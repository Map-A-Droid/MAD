import asyncio
import math
import time
from asyncio import CancelledError, Task
from typing import Any, Optional

from loguru import logger

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.helper.ScannedLocationHelper import ScannedLocationHelper
from mapadroid.db.helper.TrsStatusHelper import TrsStatusHelper
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.mapping_manager import MappingManager
from mapadroid.mapping_manager.MappingManagerDevicemappingKey import \
    MappingManagerDevicemappingKey
from mapadroid.utils.collections import Location
from mapadroid.utils.madGlobals import (
    InternalStopWorkerException, RoutemanagerShuttingDown,
    WebsocketWorkerConnectionClosedException, WebsocketWorkerRemovedException,
    WebsocketWorkerTimeoutException, application_args)
from mapadroid.utils.resolution import ResolutionCalculator
from mapadroid.utils.routeutil import check_walker_value_type
from mapadroid.worker.AbstractWorker import AbstractWorker
from mapadroid.worker.WorkerState import WorkerState
from mapadroid.worker.WorkerType import WorkerType
from mapadroid.worker.strategy.AbstractWorkerStrategy import \
    AbstractWorkerStrategy
from mapadroid.worker.strategy.StrategyFactory import StrategyFactory


class Worker(AbstractWorker):
    def __init__(self,
                 worker_state: WorkerState,
                 mapping_manager: MappingManager,
                 db_wrapper: DbWrapper,
                 scan_strategy: AbstractWorkerStrategy,
                 strategy_factory: StrategyFactory):
        AbstractWorker.__init__(self, scan_strategy=scan_strategy)
        self._mapping_manager: MappingManager = mapping_manager
        self._db_wrapper: DbWrapper = db_wrapper
        self._worker_state: WorkerState = worker_state
        self._strategy_factory = strategy_factory

        self._resocalc = ResolutionCalculator()

        self.workerstart = None
        # Async relevant variables that are initiated in start_worker
        self._work_mutex: Optional[asyncio.Lock] = None
        self._worker_task: Optional[Task] = None
        self._scan_task: Optional[Task] = None
        self._work_mutex: asyncio.Lock = asyncio.Lock()

    async def _scan_strategy_changed(self):
        async with self._work_mutex:
            if self._scan_task:
                self._scan_task.cancel()

    async def cancel_scan(self) -> None:
        async with self._work_mutex:
            if self._scan_task:
                self._scan_task.cancel()

    async def set_devicesettings_value(self, key: MappingManagerDevicemappingKey, value: Optional[Any]):
        await self._mapping_manager.set_devicesetting_value_of(self._worker_state.origin, key, value)

    async def get_devicesettings_value(self, key: MappingManagerDevicemappingKey, default_value: Optional[Any] = None):
        logger.debug("Fetching devicemappings")
        try:
            value = await self._mapping_manager.get_devicesetting_value_of_device(self._worker_state.origin, key)
        except (EOFError, FileNotFoundError) as e:
            logger.warning("Failed fetching devicemappings with description: {}. Stopping worker", e)
            raise InternalStopWorkerException("Failed fetching devicemappings")
        return value if value is not None else default_value

    async def check_max_walkers_reached(self):
        """

        Returns: False if the worker is supposed to switch strategies in order to comply with the max walkers value

        """
        if not self._scan_strategy.walker:
            return True
        reg_workers = await self._mapping_manager.routemanager_get_registered_workers(
            self._scan_strategy.area_id)
        if self._scan_strategy.walker.max_walkers and len(reg_workers) > int(
                self._scan_strategy.walker.max_walkers):
            return False
        return True

    async def start_worker(self) -> Optional[Task]:
        """
        Starts the worker in the same loop that is calling this method. Returns the task being executed.
        Returns:

        """
        async with self._work_mutex:
            if self._worker_task and self._worker_task.done():
                self._worker_task = None
            if self._worker_task:
                logger.warning("Task has not been removed before and is still running.")
                return self._worker_task
            else:
                logger.info("Starting worker task")
                loop = asyncio.get_running_loop()
                self._worker_task = loop.create_task(self._run())
                return self._worker_task

    async def _start_of_new_strategy(self) -> None:
        self.workerstart = math.floor(time.time())

        self._worker_state.last_location = await self.get_devicesettings_value(
            MappingManagerDevicemappingKey.LAST_LOCATION, None)
        if await self.get_devicesettings_value(MappingManagerDevicemappingKey.LAST_MODE) in (WorkerType.RAID_MITM.value,
                                                                                             WorkerType.MON_MITM.value,
                                                                                             WorkerType.IV_MITM.value):
            # Reset last_location - no useless waiting delays (otherwise stop mode)
            self._worker_state.last_location = Location(0.0, 0.0)

        await self.set_devicesettings_value(MappingManagerDevicemappingKey.LAST_MODE,
                                            await self._mapping_manager.routemanager_get_mode(
                                                self._scan_strategy.area_id))
        await self._scan_strategy.worker_specific_setup_start()

    async def stop_worker(self):
        if self._worker_state.stop_worker_event.is_set():
            logger.info('Worker already stopped - waiting for it')
            return
        else:
            self._worker_state.stop_worker_event.set()
            logger.info("Worker stop called")
        async with self._work_mutex:
            if self._worker_task:
                self._worker_task.cancel()
        await self._scan_strategy.worker_specific_setup_stop()

    async def _cleanup_current(self):
        try:
            await self._mapping_manager.unregister_worker_from_routemanager(self._scan_strategy.area_id,
                                                                            self._worker_state.origin)
        except ConnectionResetError as e:
            logger.warning("Failed unregistering from routemanager, routemanager may have stopped running already."
                           "Exception: {}", e)

    async def _run(self) -> None:
        with logger.contextualize(identifier=self._worker_state.origin, name="worker"):
            try:
                loop = asyncio.get_running_loop()
                self._worker_state.stop_worker_event.clear()
                while True:
                    logger.info("Starting scan strategy...")
                    while not self.get_communicator() or not await self.get_communicator().is_alive():
                        logger.debug2("No active connection present...")
                        await asyncio.sleep(1)
                    async with self._work_mutex:
                        self._scan_task = loop.create_task(self._run_scan())
                    try:
                        await self._scan_task
                    except CancelledError as e:
                        logger.warning(
                            "Scan task was cancelled externally, assuming the strategy was changed (for now...)")
                        # If the strategy was changed externally, we do not want to update it, all other cases should
                        #  be handled accordingly
                    except (InternalStopWorkerException, WebsocketWorkerTimeoutException,
                            WebsocketWorkerConnectionClosedException) as e:
                        logger.info("Websocket connectivity issues or stop was issued internally")
                    except RoutemanagerShuttingDown as e:
                        logger.info("Routemanager is shutting down, moving on through walker.")
                    finally:
                        await asyncio.sleep(5)
                        async with self._work_mutex:
                            self._scan_task = None
                        await self.__update_strategy()
            except (CancelledError,
                    asyncio.TimeoutError,
                    WebsocketWorkerRemovedException) as e:
                logger.info("Worker task cancelled or websocket worker removed")
            except Exception as e:
                logger.error("Unhandled exception in scan task: {}", e)
                logger.exception(e)
            finally:
                logger.info("Stopping worker task")
                async with self._work_mutex:
                    if self._scan_task:
                        self._scan_task.cancel()
                        await self._scan_strategy.worker_specific_setup_stop()
                    self._scan_task = None

    async def _run_scan(self):
        with logger.contextualize(identifier=self._worker_state.origin, name="worker"):
            await self._start_of_new_strategy()
            await self._scan_strategy.pre_work_loop()

            if not await self.check_max_walkers_reached():
                logger.warning('Max. Walkers in Area {}.',
                               await self._mapping_manager.routemanager_get_name(
                                   self._scan_strategy.area_id))
                await self.set_devicesettings_value(MappingManagerDevicemappingKey.FINISHED, True)
                await self._cleanup_current()
                return

            while not self._worker_state.stop_worker_event.is_set():
                # TODO: consider getting results of health checks and aborting the entire worker?
                walkercheck = await self.check_walker()
                if not walkercheck:
                    logger.info("Switching strategy (e.g., because of walker settings")
                    break

                async with self._work_mutex:
                    if not await self._scan_strategy.health_check():
                        logger.warning("Scan strategy health check turned out to be negative")
                        break

                await self._scan_strategy.grab_next_location()

                logger.debug('Checking if new location is valid')
                if not await self._scan_strategy.check_location_is_valid():
                    logger.warning("Location is invalid")
                    break

                await self._scan_strategy.pre_location_update()

                last_location: Location = await self.get_devicesettings_value(
                    MappingManagerDevicemappingKey.LAST_LOCATION, Location(0.0, 0.0))
                logger.debug2('Last location: {}, Current location: {}',
                              last_location,
                              self._worker_state.current_location)
                time_snapshot = await self._scan_strategy.move_to_location()

                if time_snapshot:
                    self._worker_state.location_count += 1
                    logger.debug("Setting new 'scannedlocation' in Database")
                    loop = asyncio.get_running_loop()
                    loop.create_task(
                        self.update_scanned_location(self._worker_state.current_location.lat,
                                                     self._worker_state.current_location.lng,
                                                     time_snapshot))

                    # TODO: Re-add encounter_all setting PROPERLY, not in WorkerBase
                    await self._scan_strategy.post_move_location_routine(time_snapshot)

                    logger.debug("Worker finished one iteration")

    async def __get_current_strategy_to_use(self, set_finished=False) -> Optional[AbstractWorkerStrategy]:
        if set_finished:
            await self.set_devicesettings_value(MappingManagerDevicemappingKey.FINISHED, True)
            await self._cleanup_current()
        device_paused: bool = not await self._mapping_manager.is_device_active(
            self._worker_state.device_id)
        configmode: bool = application_args.config_mode
        paused_or_config: bool = device_paused or configmode
        scan_strategy: Optional[AbstractWorkerStrategy] = await self._strategy_factory \
            .get_strategy_using_settings(self._worker_state.origin,
                                         enable_configmode=paused_or_config,
                                         communicator=self._scan_strategy.get_communicator(),
                                         worker_state=self._worker_state)
        return scan_strategy

    async def __update_strategy(self):
        device_paused: bool = not await self._mapping_manager.is_device_active(
            self._worker_state.device_id)
        configmode: bool = application_args.config_mode
        paused_or_config: bool = device_paused or configmode
        if not paused_or_config:
            scan_strategy: Optional[AbstractWorkerStrategy] = await self.__get_current_strategy_to_use(set_finished=True)
            if scan_strategy:
                await self.set_scan_strategy(scan_strategy)

    async def update_scanned_location(self, latitude: float, longitude: float, _timestamp: float):
        async with self._db_wrapper as session, session:
            try:
                await ScannedLocationHelper.set_scanned_location(session, latitude, longitude, _timestamp)
                await session.commit()
            except Exception as e:
                logger.warning("Failed saving scanned location of {}: {}", self._worker_state.origin, e)

    async def __area_middle_of_current_fence(self) -> Optional[Location]:
        geofence_helper: Optional[GeofenceHelper] = await self._mapping_manager.routemanager_get_geofence_helper(
            self._scan_strategy.area_id)
        location: Optional[Location] = None
        if geofence_helper:
            lat, lng = geofence_helper.get_middle_from_fence()
            location = Location(lat, lng)
        return location

    async def check_walker(self):
        if not self._scan_strategy.walker:
            logger.warning("No walker set")
            # TODO: Somehow check if some switching should be happening and when...
            #  Eventually, that should be handled by some other entity
            scan_strategy: Optional[AbstractWorkerStrategy] = await self.__get_current_strategy_to_use()
            return scan_strategy is None
        mode = self._scan_strategy.walker.algo_type
        walkereventid = self._scan_strategy.walker.eventid
        if walkereventid is not None and walkereventid != self._worker_state.active_event.get_current_event_id():
            logger.warning("Some other Event has started - leaving now")
            return False
        if mode == "countdown":
            logger.info("Checking walker mode 'countdown'")
            countdown = self._scan_strategy.walker.algo_value
            if not countdown:
                logger.error("No Value for Mode - check your settings! Killing worker")
                return False
            if self.workerstart is None or math.floor(time.time()) >= int(self.workerstart) + int(countdown):
                return False
            return True
        elif mode == "timer":
            logger.debug("Checking walker mode 'timer'")
            exittime = self._scan_strategy.walker.algo_value
            if not exittime or ':' not in exittime:
                logger.error("No or wrong Value for Mode - check your settings! Killing worker")
                return False
            # Fetch middle of geofence included..
            return check_walker_value_type(exittime, await self.__area_middle_of_current_fence())
        elif mode == "round":
            logger.debug("Checking walker mode 'round'")
            rounds = self._scan_strategy.walker.algo_value
            if len(rounds) == 0:
                logger.error("No Value for Mode - check your settings! Killing worker")
                return False
            processed_rounds = await self._mapping_manager.routemanager_get_rounds(
                self._scan_strategy.area_id,
                self._worker_state.origin)
            if int(processed_rounds) >= int(rounds):
                return False
            return True
        elif mode == "period":
            logger.debug("Checking walker mode 'period'")
            period = self._scan_strategy.walker.algo_value
            if len(period) == 0:
                logger.error("No Value for Mode - check your settings! Killing worker")
                return False
            return check_walker_value_type(period, await self.__area_middle_of_current_fence())
        elif mode == "coords":
            exittime = self._scan_strategy.walker.algo_value
            logger.debug("Routemode coords, exittime {}", exittime)
            if exittime:  # TODO: Check if routemanager still has coords (e.g. questmode should make this one stop?)
                return check_walker_value_type(exittime, await self.__area_middle_of_current_fence())
            return True
        elif mode == "idle":
            logger.debug("Checking walker mode 'idle'")
            if len(self._scan_strategy.walker.algo_value) == 0:
                logger.error("Wrong Value for mode - check your settings! Killing worker")
                return False
            sleeptime = self._scan_strategy.walker.algo_value
            logger.info('going to sleep')
            killpogo = False
            if check_walker_value_type(sleeptime, await self.__area_middle_of_current_fence()):
                await self._scan_strategy.stop_pogo()
                killpogo = True
                logger.debug("Setting device to idle for routemanager")
                async with self._db_wrapper as session, session:
                    await TrsStatusHelper.save_idle_status(session, self._db_wrapper.get_instance_id(),
                                                           self._worker_state.device_id, 0)
                    await session.commit()
            while (not self._worker_state.stop_worker_event.is_set()
                   and check_walker_value_type(sleeptime, await self.__area_middle_of_current_fence())):
                await asyncio.sleep(1)
            logger.info('just woke up')
            if killpogo:
                await self._scan_strategy.start_pogo()
            return False
        else:
            logger.error("Unknown walker mode! Killing worker")
            return False

    def set_geofix_sleeptime(self, sleeptime: int) -> bool:
        self._worker_state.current_sleep_duration = sleeptime
        return True

    async def _check_location_is_valid(self) -> bool:
        if self._worker_state.current_location is None:
            # there are no more coords - so worker is finished successfully
            await self.set_devicesettings_value(MappingManagerDevicemappingKey.FINISHED, True)
            await self._cleanup_current()
            return False
        elif self._worker_state.current_location is not None:
            # TODO: Rather check whether the location is within the geofence?
            logger.debug2('Coords are valid')
            return True

    def is_stopping(self) -> bool:
        return self._worker_state.stop_worker_event.is_set()
