import asyncio
import math
import os
import time
from abc import abstractmethod, ABC
from asyncio import Task
from enum import Enum
from typing import Dict, Optional, Any

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.helper.ScannedLocationHelper import ScannedLocationHelper
from mapadroid.db.helper.TrsStatusHelper import TrsStatusHelper
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.mapping_manager import MappingManager
from mapadroid.mapping_manager.MappingManagerDevicemappingKey import MappingManagerDevicemappingKey
from mapadroid.mitm_receiver.MitmMapper import MitmMapper
from mapadroid.ocr.pogoWindows import PogoWindows
from mapadroid.ocr.screenPath import WordToScreenMatching
from mapadroid.ocr.screen_type import ScreenType
from mapadroid.utils.collections import Location
from mapadroid.utils.logging import LoggerEnums, get_logger
from mapadroid.utils.madGlobals import (
    InternalStopWorkerException, ScreenshotType,
    WebsocketWorkerConnectionClosedException, WebsocketWorkerRemovedException,
    WebsocketWorkerTimeoutException)
from mapadroid.utils.resolution import Resocalculator
from mapadroid.utils.routeutil import check_walker_value_type
from mapadroid.websocket.AbstractCommunicator import AbstractCommunicator
from mapadroid.worker.AbstractWorker import AbstractWorker
from mapadroid.worker.WorkerType import WorkerType

logger = get_logger(LoggerEnums.worker)


class FortSearchResultTypes(Enum):
    UNDEFINED = 0
    QUEST = 1
    TIME = 2
    COOLDOWN = 3
    INVENTORY = 4
    LIMIT = 5
    UNAVAILABLE = 6
    OUT_OF_RANGE = 7
    FULL = 8


class WorkerBase(AbstractWorker, ABC):
    def __init__(self, args, dev_id, origin, last_known_state, communicator: AbstractCommunicator,
                 mapping_manager: MappingManager,
                 area_id: int, routemanager_id: int, db_wrapper: DbWrapper, pogo_window_manager: PogoWindows,
                 walker: Dict = None, event=None):
        AbstractWorker.__init__(self, origin=origin, communicator=communicator)
        self._mapping_manager: MappingManager = mapping_manager
        self._routemanager_id: int = routemanager_id
        self._area_id = area_id
        self._dev_id: int = dev_id
        self._event = event
        self._origin: str = origin
        self._applicationArgs = args
        self._last_known_state = last_known_state
        self._location_count = 0
        self._walker: Dict = walker
        self._lastScreenshotTaken = 0
        self._db_wrapper: DbWrapper = db_wrapper
        self._resocalc = Resocalculator
        self._screen_x = 0
        self._screen_y = 0
        self._geofix_sleeptime = 0
        self._pogoWindowManager = pogo_window_manager
        self._waittime_without_delays = 0
        self._transporttype = 0
        self._not_injected_count: int = 0
        self._same_screen_count: int = 0
        self._last_screen_type: ScreenType = ScreenType.UNDEFINED
        self._loginerrorcounter: int = 0
        self._wait_again: int = 0
        self.current_location = Location(0.0, 0.0)
        self.last_location = Location(0.0, 0.0)
        self.workerstart = None

        # Async relevant variables that are initiated in start_worker
        self._work_mutex: Optional[asyncio.Lock] = None
        self._init: bool = False
        self._stop_worker_event: Optional[asyncio.Event] = None
        self._mode: WorkerType = WorkerType.UNDEFINED
        self._levelmode: bool = False
        self._geofencehelper: Optional[GeofenceHelper] = None
        self._word_to_screen_matching: Optional[WordToScreenMatching] = None

    async def set_devicesettings_value(self, key: MappingManagerDevicemappingKey, value: Optional[Any]):
        await self._mapping_manager.set_devicesetting_value_of(self._origin, key, value)

    async def get_devicesettings_value(self, key: MappingManagerDevicemappingKey, default_value: Optional[Any] = None):
        self.logger.debug("Fetching devicemappings")
        try:
            value = await self._mapping_manager.get_devicesetting_value_of_device(self.origin, key)
        except (EOFError, FileNotFoundError) as e:
            self.logger.warning("Failed fetching devicemappings with description: {}. Stopping worker", e)
            self._stop_worker_event.set()
            return None
        return value if value else default_value

    async def get_screenshot_path(self, fileaddon: bool = False) -> str:
        screenshot_ending: str = ".jpg"
        addon: str = ""
        if await self.get_devicesettings_value(MappingManagerDevicemappingKey.SCREENSHOT_TYPE, "jpeg") == "png":
            screenshot_ending = ".png"

        if fileaddon:
            addon: str = "_" + str(time.time())

        screenshot_filename = "screenshot_{}{}{}".format(str(self._origin), str(addon), screenshot_ending)

        if fileaddon:
            self.logger.info("Creating debugscreen: {}", screenshot_filename)

        return os.path.join(
            self._applicationArgs.temp_path, screenshot_filename)

    async def check_max_walkers_reached(self):
        walkermax = self._walker.get('walkermax', False)
        if walkermax is False or (type(walkermax) is str and len(walkermax) == 0):
            return True
        reg_workers = await self._mapping_manager.routemanager_get_registered_workers(self._routemanager_id)
        if len(reg_workers) > int(walkermax):
            return False
        return True

    @abstractmethod
    async def _pre_work_loop(self):
        """
        Work to be done before the main while true work-loop
        Start off asyncio loops etc in here
        :return:
        """
        pass

    @abstractmethod
    async def _health_check(self):
        """
        Health check before a location is grabbed. Internally, a self._start_pogo call is already executed since
        that usually includes a topmost check
        :return:
        """
        pass

    @abstractmethod
    async def _pre_location_update(self):
        """
        Override to run stuff like update injections settings in MITM worker
        Runs before walk/teleport to the location previously grabbed
        :return:
        """
        pass

    @abstractmethod
    async def _move_to_location(self):
        """
        Location has previously been grabbed, the overriden function will be called.
        You may teleport or walk by your choosing
        Any post walk/teleport delays/sleeps have to be run in the derived, override method
        :return:
        """
        pass

    @abstractmethod
    async def _post_move_location_routine(self, timestamp):
        """
        Routine called after having moved to a new location. MITM worker e.g. has to wait_for_data
        :param timestamp:
        :return:
        """

    @abstractmethod
    async def _cleanup(self):
        """
        Cleanup any threads you started in derived classes etc
        self.stop_worker() and self.loop.stop() will be called afterwards
        :return:
        """

    @abstractmethod
    async def _worker_specific_setup_start(self):
        """
        Routine preparing the state to scan. E.g. starting specific apps or clearing certain files
        Returns:
        """

    @abstractmethod
    async def _worker_specific_setup_stop(self):
        """
        Routine destructing the state to scan. E.g. stopping specific apps or clearing certain files
        Returns:
        """

    async def start_worker(self) -> Task:
        """
        Starts the worker in the same loop that is calling this method. Returns the task being executed.
        Returns:

        """
        loop = asyncio.get_event_loop()

        self._work_mutex: asyncio.Lock = asyncio.Lock()
        self._init: bool = await self._mapping_manager.routemanager_get_init(self._routemanager_id)
        self._stop_worker_event: asyncio.Event = asyncio.Event()
        self._mode: WorkerType = await self._mapping_manager.routemanager_get_mode(self._routemanager_id)
        self._levelmode: bool = await self._mapping_manager.routemanager_get_level(self._routemanager_id)
        self._geofencehelper: Optional[GeofenceHelper] = await self._mapping_manager.routemanager_get_geofence_helper(
            self._routemanager_id)
        self.last_location: Optional[Location] = await self.get_devicesettings_value(
            MappingManagerDevicemappingKey.LAST_LOCATION, None)
        self._word_to_screen_matching = await WordToScreenMatching.create(self._communicator, self._pogoWindowManager,
                                                                          self._origin,
                                                                          self._resocalc, self._mapping_manager,
                                                                          self._applicationArgs)

        if await self.get_devicesettings_value(MappingManagerDevicemappingKey.LAST_MODE) in ("raids_mitm", "mon_mitm",
                                                                                             "iv_mitm"):
            # Reset last_location - no useless waiting delays (otherwise stop mode)
            self.last_location = Location(0.0, 0.0)

        await self.set_devicesettings_value(MappingManagerDevicemappingKey.LAST_MODE,
                                            await self._mapping_manager.routemanager_get_mode(
                                                self._routemanager_id))
        return loop.create_task(self._main_work_thread())

    async def stop_worker(self):
        if self._stop_worker_event.set():
            self.logger.info('Worker already stopped - waiting for it')
        else:
            self._stop_worker_event.set()
            self.logger.info("Worker stop called")

    async def _internal_pre_work(self):
        # current_thread().name = self._origin

        start_position = await self.get_devicesettings_value(MappingManagerDevicemappingKey.STARTCOORDS_OF_WALKER, None)
        calc_type = await self._mapping_manager.routemanager_get_calc_type(self._routemanager_id)

        if start_position and (self._levelmode and calc_type == "routefree"):
            startcoords = (
                await self.get_devicesettings_value(MappingManagerDevicemappingKey.STARTCOORDS_OF_WALKER)).replace(' ',
                                                                                                                   '') \
                .replace('_', '').split(',')

            if not self._geofencehelper.is_coord_inside_include_geofence(Location(
                    float(startcoords[0]), float(startcoords[1]))):
                self.logger.info("Startcoords not in geofence - setting middle of fence as starting position")
                lat, lng = self._geofencehelper.get_middle_from_fence()
                start_position = str(lat) + "," + str(lng)

        if start_position is None and \
                (self._levelmode and calc_type == "routefree"):
            self.logger.info("Starting level mode without worker start position")
            # setting coords
            lat, lng = self._geofencehelper.get_middle_from_fence()
            start_position = str(lat) + "," + str(lng)

        if start_position is not None:
            startcoords = start_position.replace(' ', '').replace('_', '').split(',')

            if not self._geofencehelper.is_coord_inside_include_geofence(Location(
                    float(startcoords[0]), float(startcoords[1]))):
                self.logger.info("Startcoords not in geofence - setting middle of fence as startposition")
                lat, lng = self._geofencehelper.get_middle_from_fence()
                start_position = str(lat) + "," + str(lng)
                startcoords = start_position.replace(' ', '').replace('_', '').split(',')

            self.logger.info('Setting startcoords or walker lat {} / lng {}', startcoords[0], startcoords[1])
            await self._communicator.set_location(Location(startcoords[0], startcoords[1]), 0)

            await self._mapping_manager.set_worker_startposition(routemanager_name=self._routemanager_id,
                                                                 worker_name=self._origin,
                                                                 lat=float(startcoords[0]),
                                                                 lon=float(startcoords[1]))

        async with self._work_mutex:
            try:
                await self._turn_screen_on_and_start_pogo()
                await self._get_screen_size()
                # register worker  in routemanager
                self.logger.info("Try to register in Routemanager {}",
                                 await self._mapping_manager.routemanager_get_name(self._routemanager_id))
                await self._mapping_manager.register_worker_to_routemanager(self._routemanager_id, self._origin)
            except WebsocketWorkerRemovedException:
                self.logger.error("Timeout during init of worker")
                # no cleanup required here? TODO: signal websocket server somehow
                self._stop_worker_event.set()
                return

        await self._pre_work_loop()

    async def _internal_health_check(self):
        # check if pogo is topmost and start if necessary
        self.logger.debug4("_internal_health_check: Calling _start_pogo routine to check if pogo is topmost")
        pogo_started = False
        async with self._work_mutex:
            self.logger.debug2("_internal_health_check: worker lock acquired")
            self.logger.debug4("Checking if we need to restart pogo")
            # Restart pogo every now and then...
            restart_pogo_setting = await self.get_devicesettings_value(MappingManagerDevicemappingKey.RESTART_POGO, 0)
            if restart_pogo_setting > 0:
                if self._location_count > restart_pogo_setting:
                    self.logger.info("scanned {} locations, restarting game", restart_pogo_setting)
                    pogo_started = await self._restart_pogo()
                    self._location_count = 0
                else:
                    pogo_started = await self._start_pogo()
            else:
                pogo_started = await self._start_pogo()

        self.logger.debug4("_internal_health_check: worker lock released")
        return pogo_started

    async def _internal_cleanup(self):
        # set the event just to make sure - in case of exceptions for example
        self._stop_worker_event.set()
        try:
            await self._mapping_manager.unregister_worker_from_routemanager(self._routemanager_id, self._origin)
        except ConnectionResetError as e:
            self.logger.warning("Failed unregistering from routemanager, routemanager may have stopped running already."
                                "Exception: {}", e)
        self.logger.info("Internal cleanup of started")
        await self._cleanup()
        self.logger.info("Internal cleanup signaling end to websocketserver")
        await self._communicator.cleanup()

        self.logger.info("Internal cleanup of finished")

    async def _main_work_thread(self):
        # TODO: signal websocketserver the removal
        try:
            await self._internal_pre_work()
        except (InternalStopWorkerException, WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException,
                WebsocketWorkerConnectionClosedException):
            self.logger.error("Failed initializing worker, connection terminated exceptionally")
            await self._internal_cleanup()
            return

        if not await self.check_max_walkers_reached():
            self.logger.warning('Max. Walkers in Area {} - closing connections',
                                self._mapping_manager.routemanager_get_name(self._routemanager_id))
            await self.set_devicesettings_value(MappingManagerDevicemappingKey.FINISHED, True)
            await self._internal_cleanup()
            return

        # TODO: Async event?
        while not self._stop_worker_event.is_set():
            try:
                # TODO: consider getting results of health checks and aborting the entire worker?
                walkercheck = await self.check_walker()
                if not walkercheck:
                    await self.set_devicesettings_value(MappingManagerDevicemappingKey.FINISHED, True)
                    break
            except (InternalStopWorkerException, WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException,
                    WebsocketWorkerConnectionClosedException):
                self.logger.warning("Worker killed by walker settings")
                break

            try:
                # TODO: consider getting results of health checks and aborting the entire worker?
                await self._internal_health_check()
                await self._health_check()
            except (InternalStopWorkerException, WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException,
                    WebsocketWorkerConnectionClosedException):
                self.logger.error("Websocket connection to {} lost while running healthchecks, connection terminated "
                                  "exceptionally", self._origin)
                break

            try:
                settings = await self._internal_grab_next_location()
                if settings is None:
                    continue
            except (InternalStopWorkerException, WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException,
                    WebsocketWorkerConnectionClosedException):
                self.logger.warning("Worker of does not support mode that's to be run, connection terminated "
                                    "exceptionally")
                break

            try:
                self.logger.debug('Checking if new location is valid')
                if not await self._check_location_is_valid():
                    break
            except (InternalStopWorkerException, WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException,
                    WebsocketWorkerConnectionClosedException):
                self.logger.warning("Worker received invalid coords!")
                break

            try:
                await self._pre_location_update()
            except (InternalStopWorkerException, WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException,
                    WebsocketWorkerConnectionClosedException):
                self.logger.warning("Worker of stopping because of stop signal in pre_location_update, connection "
                                    "terminated exceptionally")
                break

            try:
                last_location: Location = await self.get_devicesettings_value(
                    MappingManagerDevicemappingKey.LAST_LOCATION, Location(0, 0))
                self.logger.debug2('LastLat: {}, LastLng: {}, CurLat: {}, CurLng: {}',
                                   last_location.lat, last_location.lng,
                                   self.current_location.lat, self.current_location.lng)
                time_snapshot, process_location = await self._move_to_location()
            except (InternalStopWorkerException, WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException,
                    WebsocketWorkerConnectionClosedException):
                self.logger.warning("Worker failed moving to new location, stopping worker, connection terminated "
                                    "exceptionally")
                break

            if process_location:
                await self._update_position_file()
                self._location_count += 1
                self.logger.debug("Seting new 'scannedlocation' in Database")
                loop = asyncio.get_event_loop()
                loop.create_task(
                    self.update_scanned_location(self.current_location.lat, self.current_location.lng, time_snapshot))

                # TODO: Re-add encounter_all setting PROPERLY, not in WorkerBase
                try:
                    await self._post_move_location_routine(time_snapshot)
                except (InternalStopWorkerException, WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException,
                        WebsocketWorkerConnectionClosedException):
                    self.logger.warning("Worker failed running post_move_location_routine, stopping worker")
                    break
                self.logger.info("Worker finished iteration, continuing work")

        await self._internal_cleanup()

    async def _update_position_file(self):
        self.logger.debug2("Updating .position file")
        if self.current_location is not None:
            with open(os.path.join(self._applicationArgs.file_path, self._origin + '.position'),
                      'w') as outfile:
                outfile.write(str(self.current_location.lat) +
                              ", " + str(self.current_location.lng))

    async def update_scanned_location(self, latitude: float, longitude: float, utc_timestamp: float):
        try:
            async with self._db_wrapper as session, session:
                await ScannedLocationHelper.set_scanned_location(session, latitude, longitude, utc_timestamp)

        except Exception as e:
            self.logger.error("Failed updating scanned location: {}", e)

    async def check_walker(self):
        mode = self._walker['walkertype']
        walkereventid = self._walker.get('eventid', None)
        if walkereventid is not None and walkereventid != self._event.get_current_event_id():
            self.logger.warning("Some other Event has started - leaving now")
            return False
        if mode == "countdown":
            self.logger.info("Checking walker mode 'countdown'")
            countdown = self._walker['walkervalue']
            if not countdown:
                self.logger.error("No Value for Mode - check your settings! Killing worker")
                return False
            if self.workerstart is None:
                self.workerstart = math.floor(time.time())
            else:
                if math.floor(time.time()) >= int(self.workerstart) + int(countdown):
                    return False
            return True
        elif mode == "timer":
            self.logger.debug("Checking walker mode 'timer'")
            exittime = self._walker['walkervalue']
            if not exittime or ':' not in exittime:
                self.logger.error("No or wrong Value for Mode - check your settings! Killing worker")
                return False
            return check_walker_value_type(exittime)
        elif mode == "round":
            self.logger.debug("Checking walker mode 'round'")
            rounds = self._walker['walkervalue']
            if len(rounds) == 0:
                self.logger.error("No Value for Mode - check your settings! Killing worker")
                return False
            processed_rounds = await self._mapping_manager.routemanager_get_rounds(self._routemanager_id,
                                                                                   self._origin)
            if int(processed_rounds) >= int(rounds):
                return False
            return True
        elif mode == "period":
            self.logger.debug("Checking walker mode 'period'")
            period = self._walker['walkervalue']
            if len(period) == 0:
                self.logger.error("No Value for Mode - check your settings! Killing worker")
                return False
            return check_walker_value_type(period)
        elif mode == "coords":
            exittime = self._walker['walkervalue']
            if len(exittime) > 0:
                return check_walker_value_type(exittime)
            return True
        elif mode == "idle":
            self.logger.debug("Checking walker mode 'idle'")
            if len(self._walker['walkervalue']) == 0:
                self.logger.error("Wrong Value for mode - check your settings! Killing worker")
                return False
            sleeptime = self._walker['walkervalue']
            self.logger.info('going to sleep')
            killpogo = False
            if check_walker_value_type(sleeptime):
                await self._stop_pogo()
                killpogo = True
            while not self._stop_worker_event.is_set() and check_walker_value_type(sleeptime):
                await asyncio.sleep(1)
            self.logger.info('just woke up')
            if killpogo:
                await self._start_pogo()
            return False
        else:
            self.logger.error("Unknown walker mode! Killing worker")
            return False

    def set_geofix_sleeptime(self, sleeptime: int) -> bool:
        self._geofix_sleeptime = sleeptime
        return True

    async def _internal_grab_next_location(self):
        # TODO: consider adding runWarningThreadEvent.set()
        self._last_known_state["last_location"] = self.last_location

        self.logger.debug("Requesting next location from routemanager")
        # requesting a location is blocking (iv_mitm will wait for a prioQ item), we really need to clean
        # the workers up...
        if int(self._geofix_sleeptime) > 0:
            self.logger.info('Getting a geofix position from MADMin - sleeping for {} seconds', self._geofix_sleeptime)
            await asyncio.sleep(int(self._geofix_sleeptime))
            self._geofix_sleeptime = 0

        await self._check_for_mad_job()

        self.current_location = await self._mapping_manager.routemanager_get_next_location(self._routemanager_id,
                                                                                           self._origin)
        self._wait_again: int = 1
        return await self._mapping_manager.routemanager_get_settings(self._routemanager_id)

    async def _check_for_mad_job(self):
        if await self.get_devicesettings_value(MappingManagerDevicemappingKey.JOB_ACTIVE, False):
            self.logger.info("Worker get a job - waiting")
            while await self.get_devicesettings_value(MappingManagerDevicemappingKey.JOB_ACTIVE,
                                                      False) and not self._stop_worker_event.is_set():
                await asyncio.sleep(10)
            self.logger.info("Worker processed the job and go on ")

    async def _check_location_is_valid(self) -> bool:
        if self.current_location is None:
            # there are no more coords - so worker is finished successfully
            await self.set_devicesettings_value(MappingManagerDevicemappingKey.FINISHED, True)
            return False
        elif self.current_location is not None:
            # TODO: WTF Weird validation....
            self.logger.debug2('Coords are valid')
            return True

    async def _turn_screen_on_and_start_pogo(self):
        if not await self._communicator.is_screen_on():
            await self._communicator.start_app("de.grennith.rgc.remotegpscontroller")
            self.logger.info("Turning screen on")
            await self._communicator.turn_screen_on()
            await asyncio.sleep(
                await self.get_devicesettings_value(MappingManagerDevicemappingKey.POST_TURN_SCREEN_ON_DELAY, 2))
        # check if pogo is running and start it if necessary
        self.logger.info("turnScreenOnAndStartPogo: (Re-)Starting Pogo")
        await self._start_pogo()

    async def _ensure_pogo_topmost(self):
        self.logger.info('Checking pogo screen...')
        screen_type: ScreenType = ScreenType.UNDEFINED
        while not self._stop_worker_event.is_set():
            # TODO: Make this not block the loop somehow... asyncio waiting for a thread?
            screen_type: ScreenType = await self._word_to_screen_matching.detect_screentype()
            if screen_type in [ScreenType.POGO, ScreenType.QUEST]:
                self._last_screen_type = screen_type
                self._loginerrorcounter = 0
                self.logger.debug2("Found pogo or questlog to be open")
                break

            if screen_type != ScreenType.ERROR and self._last_screen_type == screen_type:
                self._same_screen_count += 1
                self.logger.info("Found {} multiple times in a row ({})", screen_type, self._same_screen_count)
                if self._same_screen_count > 3:
                    self.logger.warning("Screen is frozen!")
                    if self._same_screen_count > 4 or not self._restart_pogo():
                        self.logger.warning("Restarting PoGo failed - reboot device")
                        await self._reboot()
                    break
            elif self._last_screen_type != screen_type:
                self._same_screen_count = 0

            # now handle all screens that may not have been handled by detect_screentype since that only clicks around
            # so any clearing data whatsoever happens here (for now)
            if screen_type == ScreenType.UNDEFINED:
                self.logger.error("Undefined screentype!")
            elif screen_type == ScreenType.BLACK:
                self.logger.info("Found Black Loading Screen - waiting ...")
                await asyncio.sleep(20)
            elif screen_type == ScreenType.CLOSE:
                self.logger.debug("screendetection found pogo closed, start it...")
                await self._start_pogo()
                self._loginerrorcounter += 1
            elif screen_type in [ScreenType.GAMEDATA, ScreenType.CONSENT]:
                self.logger.info('Error getting Gamedata or strange ggl message appears')
                self._loginerrorcounter += 1
                if self._loginerrorcounter < 2:
                    await self._restart_pogo_safe()
            elif screen_type == ScreenType.DISABLED:
                # Screendetection is disabled
                break
            elif screen_type == ScreenType.UPDATE:
                self.logger.warning(
                    'Found update pogo screen - sleeping 5 minutes for another check of the screen')
                # update pogo - later with new rgc version
                await asyncio.sleep(300)
            elif screen_type in [ScreenType.ERROR, ScreenType.FAILURE]:
                self.logger.warning('Something wrong with screendetection or pogo failure screen')
                self._loginerrorcounter += 1
            elif screen_type == ScreenType.NOGGL:
                self.logger.warning('Detected login select screen missing the Google'
                                    ' button - likely entered an invalid birthdate previously')
                self._loginerrorcounter += 1
            elif screen_type == ScreenType.GPS:
                self.logger.warning("Detected GPS error - reboot device")
                await self._reboot()
                break
            elif screen_type == ScreenType.SN:
                self.logger.warning('Getting SN Screen - restart PoGo and later PD')
                await self._restart_pogo_safe()
                break

            if self._loginerrorcounter > 1:
                self.logger.warning('Could not login again - (clearing game data + restarting device')
                await self._stop_pogo()
                await self._communicator.clear_app_cache("com.nianticlabs.pokemongo")
                if await self.get_devicesettings_value(MappingManagerDevicemappingKey.CLEAR_GAME_DATA, False):
                    self.logger.info('Clearing game data')
                    await self._communicator.reset_app_data("com.nianticlabs.pokemongo")
                self._loginerrorcounter = 0
                await self._reboot()
                break

            self._last_screen_type = screen_type
        self.logger.info('Checking pogo screen is finished')
        if screen_type in [ScreenType.POGO, ScreenType.QUEST]:
            return True
        else:
            return False

    async def _restart_pogo_safe(self):
        self.logger.info("WorkerBase::_restart_pogo_safe restarting pogo the long way")
        await self._stop_pogo()
        await asyncio.sleep(1)
        if self._applicationArgs.enable_worker_specific_extra_start_stop_handling:
            await self._worker_specific_setup_stop()
            await asyncio.sleep(1)
        await self._communicator.magisk_off()
        await asyncio.sleep(1)
        await self._communicator.magisk_on()
        await asyncio.sleep(1)
        await self._communicator.start_app("com.nianticlabs.pokemongo")
        await asyncio.sleep(25)
        await self._stop_pogo()
        await asyncio.sleep(1)
        if self._applicationArgs.enable_worker_specific_extra_start_stop_handling:
            await self._worker_specific_setup_start()
            await asyncio.sleep(1)
        return await self._start_pogo()

    async def _switch_user(self):
        self.logger.info('Switching User - please wait ...')
        await self._stop_pogo()
        await asyncio.sleep(5)
        await self._communicator.reset_app_data("com.nianticlabs.pokemongo")
        await self._turn_screen_on_and_start_pogo()
        if not self._ensure_pogo_topmost():
            self.logger.error('Kill Worker...')
            self._stop_worker_event.set()
            return False
        self.logger.info('Switching finished ...')
        return True

    async def _start_pogo(self) -> bool:
        """
        Routine to start pogo.
        Return the state as a boolean do indicate a successful start
        :return:
        """
        pogo_topmost = await self._communicator.is_pogo_topmost()
        if pogo_topmost:
            return True

        if not await self._communicator.is_screen_on():
            await self._communicator.start_app("de.grennith.rgc.remotegpscontroller")
            self.logger.info("Turning screen on")
            await self._communicator.turn_screen_on()
            await asyncio.sleep(
                await self.get_devicesettings_value(MappingManagerDevicemappingKey.POST_TURN_SCREEN_ON_DELAY, 7))

        cur_time = time.time()
        start_result = False
        attempts = 0
        while not pogo_topmost:
            attempts += 1
            if attempts > 10:
                self.logger.warning("_start_pogo failed 10 times")
                return False
            start_result = await self._communicator.start_app("com.nianticlabs.pokemongo")
            await asyncio.sleep(1)
            pogo_topmost = await self._communicator.is_pogo_topmost()

        if start_result:
            self.logger.success("startPogo: Started pogo successfully...")
            self._last_known_state["lastPogoRestart"] = cur_time

        await self._wait_pogo_start_delay()
        return start_result

    def is_stopping(self) -> bool:
        return self._stop_worker_event.is_set()

    async def _stop_pogo(self):
        attempts = 0
        stop_result = await self._communicator.stop_app("com.nianticlabs.pokemongo")
        pogo_topmost = await self._communicator.is_pogo_topmost()
        while pogo_topmost:
            attempts += 1
            if attempts > 10:
                return False
            stop_result = await self._communicator.stop_app("com.nianticlabs.pokemongo")
            await asyncio.sleep(1)
            pogo_topmost = await self._communicator.is_pogo_topmost()
        return stop_result

    async def _reboot(self, mitm_mapper: Optional[MitmMapper] = None):
        try:
            start_result = await self._communicator.reboot()
        except WebsocketWorkerRemovedException:
            self.logger.error("Could not reboot due to client already disconnected")
            start_result = False
        await asyncio.sleep(5)
        if mitm_mapper is not None:
            await mitm_mapper.collect_location_stats(self._origin, self.current_location, 1, time.time(), 3, 0,
                                                     self._mapping_manager.routemanager_get_mode(
                                                         self._routemanager_id),
                                                     99)
        async with self._db_wrapper as session, session:
            await TrsStatusHelper.save_last_reboot(session, self._db_wrapper.get_instance_id(), self._dev_id)
        self._reboot_count = 0
        self._restart_count = 0
        await self.stop_worker()
        return start_result

    async def _restart_pogo(self, clear_cache=True, mitm_mapper: Optional[MitmMapper] = None):
        successful_stop = self._stop_pogo()
        async with self._db_wrapper as session, session:
            await TrsStatusHelper.save_last_restart(session, self._db_wrapper.get_instance_id(), self._dev_id)
        self._restart_count = 0
        self.logger.debug("restartPogo: stop game resulted in {}", str(successful_stop))
        if successful_stop:
            if clear_cache:
                await self._communicator.clear_app_cache("com.nianticlabs.pokemongo")
            await asyncio.sleep(1)
            if mitm_mapper is not None:
                await mitm_mapper.collect_location_stats(self._origin, self.current_location, 1, time.time(), 4, 0,
                                                         self._mapping_manager.routemanager_get_mode(
                                                             self._routemanager_id),
                                                         99)
            return await self._start_pogo()
        else:
            self.logger.warning("Failed restarting PoGo - reboot device")
            return await self._reboot()

    async def _get_trash_positions(self, full_screen=False):
        self.logger.debug2("_get_trash_positions: Get_trash_position.")
        if not await self._take_screenshot(
                delay_before=await self.get_devicesettings_value(MappingManagerDevicemappingKey.POST_SCREENSHOT_DELAY,
                                                                 1)):
            self.logger.debug("_get_trash_positions: Failed getting screenshot")
            return None

        if os.path.isdir(await self.get_screenshot_path()):
            self.logger.error("_get_trash_positions: screenshot.png is not a file/corrupted")
            return None

        self.logger.debug2("_get_trash_positions: checking screen")
        trashes = await self._pogoWindowManager.get_trash_click_positions(self._origin,
                                                                          await self.get_screenshot_path(),
                                                                          full_screen=full_screen)

        return trashes

    async def _take_screenshot(self, delay_after=0.0, delay_before=0.0, errorscreen: bool = False):
        self.logger.debug2("Taking screenshot...")
        await asyncio.sleep(delay_before)
        time_since_last_screenshot = time.time() - self._lastScreenshotTaken
        self.logger.debug4("Last screenshot taken: {}", str(self._lastScreenshotTaken))

        # TODO: area settings for jpg/png and quality?
        screenshot_type: ScreenshotType = ScreenshotType.JPEG
        if await self.get_devicesettings_value(MappingManagerDevicemappingKey.SCREENSHOT_TYPE, "jpeg") == "png":
            screenshot_type = ScreenshotType.PNG

        screenshot_quality: int = await self.get_devicesettings_value(MappingManagerDevicemappingKey.SCREENSHOT_QUALITY,
                                                                      80)

        take_screenshot = await self._communicator.get_screenshot(await self.get_screenshot_path(fileaddon=errorscreen),
                                                                  screenshot_quality, screenshot_type)

        if self._lastScreenshotTaken and time_since_last_screenshot < 0.5:
            self.logger.info("screenshot taken recently, returning immediately")
            return True
        elif not take_screenshot:
            self.logger.warning("Failed retrieving screenshot")
            return False
        else:
            self.logger.debug("Success retrieving screenshot")
            self._lastScreenshotTaken = time.time()
            await asyncio.sleep(delay_after)
            return True

    async def _check_pogo_main_screen(self, max_attempts, again=False):
        self.logger.debug("_check_pogo_main_screen: Trying to get to the Mainscreen with {} max attempts...",
                          max_attempts)
        pogo_topmost = await self._communicator.is_pogo_topmost()
        if not pogo_topmost:
            return False

        if not await self._take_screenshot(
                delay_before=await self.get_devicesettings_value(MappingManagerDevicemappingKey.POST_SCREENSHOT_DELAY,
                                                                 1)):
            if again:
                self.logger.warning("_check_pogo_main_screen: failed getting a screenshot again")
                return False
        attempts = 0

        screenshot_path = await self.get_screenshot_path()
        if os.path.isdir(screenshot_path):
            self.logger.error("_check_pogo_main_screen: screenshot.png/.jpg is not a file/corrupted")
            return False

        self.logger.debug("_check_pogo_main_screen: checking mainscreen")
        while not await self._pogoWindowManager.check_pogo_mainscreen(screenshot_path, self._origin):
            self.logger.info("_check_pogo_main_screen: not on Mainscreen...")
            if attempts == max_attempts:
                # could not reach raidtab in given max_attempts
                self.logger.warning("_check_pogo_main_screen: Could not get to Mainscreen within {} attempts",
                                    max_attempts)
                return False

            found = await self._pogoWindowManager.check_close_except_nearby_button(await self.get_screenshot_path(),
                                                                                   self._origin,
                                                                                   self._communicator,
                                                                                   close_raid=True)
            if found:
                self.logger.debug("_check_pogo_main_screen: Found (X) button (except nearby)")

            if not found and await self._pogoWindowManager.look_for_button(self._origin, screenshot_path, 2.20, 3.01,
                                                                           self._communicator):
                self.logger.debug("_check_pogo_main_screen: Found button (small)")
                found = True

            if not found and await self._pogoWindowManager.look_for_button(self._origin, screenshot_path, 1.05, 2.20,
                                                                           self._communicator):
                self.logger.debug("_check_pogo_main_screen: Found button (big)")
                await asyncio.sleep(5)
                found = True

            self.logger.debug("_check_pogo_main_screen: Previous checks found pop ups: {}", found)

            await self._take_screenshot(
                delay_before=await self.get_devicesettings_value(MappingManagerDevicemappingKey.POST_SCREENSHOT_DELAY,
                                                                 1))

            attempts += 1
        self.logger.debug("_check_pogo_main_screen: done")
        return True

    async def _check_pogo_button(self):
        self.logger.debug("checkPogoButton: Trying to find buttons")
        pogo_topmost = await self._communicator.is_pogo_topmost()
        if not pogo_topmost:
            return False
        if not await self._take_screenshot(
                delay_before=await self.get_devicesettings_value(MappingManagerDevicemappingKey.POST_SCREENSHOT_DELAY,
                                                                 1)):
            self.logger.debug("checkPogoButton: Failed getting screenshot")
            return False
        # TODO: os operation asyncio?
        if os.path.isdir(await self.get_screenshot_path()):
            self.logger.error("checkPogoButton: screenshot.png is not a file/corrupted")
            return False

        self.logger.debug("checkPogoButton: checking for buttons")
        # TODO: need to be non-blocking
        found = await self._pogoWindowManager.look_for_button(self._origin, await self.get_screenshot_path(), 2.20,
                                                              3.01,
                                                              self._communicator)
        if found:
            await asyncio.sleep(1)
            self.logger.debug("checkPogoButton: Found button (small)")

        if not found and await self._pogoWindowManager.look_for_button(self._origin, await self.get_screenshot_path(),
                                                                       1.05, 2.20,
                                                                       self._communicator):
            self.logger.debug("checkPogoButton: Found button (big)")
            found = True

        self.logger.debug("checkPogoButton: done")
        return found

    async def _wait_pogo_start_delay(self):
        delay_count: int = 0
        pogo_start_delay: int = await self.get_devicesettings_value(
            MappingManagerDevicemappingKey.POST_POGO_START_DELAY, 60)
        self.logger.info('Waiting for pogo start: {} seconds', pogo_start_delay)

        while delay_count <= pogo_start_delay:
            if not await self._mapping_manager.routemanager_present(self._routemanager_id) \
                    or self._stop_worker_event.is_set():
                self.logger.error("Killed while waiting for pogo start")
                raise InternalStopWorkerException
            await asyncio.sleep(1)
            delay_count += 1

    async def _check_pogo_close(self, takescreen=True):
        self.logger.debug("checkPogoClose: Trying to find closeX")
        if not await self._communicator.is_pogo_topmost():
            return False

        if takescreen:
            if not await self._take_screenshot(delay_before=await self.get_devicesettings_value(
                    MappingManagerDevicemappingKey.POST_SCREENSHOT_DELAY, 1)):
                self.logger.debug("checkPogoClose: Could not get screenshot")
                return False

        # TODO: Async...
        if os.path.isdir(await self.get_screenshot_path()):
            self.logger.error("checkPogoClose: screenshot.png is not a file/corrupted")
            return False

        self.logger.debug("checkPogoClose: checking for CloseX")
        found = await self._pogoWindowManager.check_close_except_nearby_button(self.get_screenshot_path(),
                                                                               self._origin,
                                                                               self._communicator)
        if found:
            await asyncio.sleep(1)
            self.logger.debug("checkPogoClose: Found (X) button (except nearby)")
            self.logger.debug("checkPogoClose: done")
            return True
        self.logger.debug("checkPogoClose: done")
        return False

    async def _get_screen_size(self):
        if self._stop_worker_event.is_set():
            raise WebsocketWorkerRemovedException
        screen = await self._communicator.get_screensize()
        if screen is None:
            raise WebsocketWorkerRemovedException
        screen = screen.strip().split(' ')
        self._screen_x = screen[0]
        self._screen_y = screen[1]
        x_offset = await self.get_devicesettings_value(MappingManagerDevicemappingKey.SCREENSHOT_X_OFFSET, 0)
        y_offset = await self.get_devicesettings_value(MappingManagerDevicemappingKey.SCREENSHOT_Y_OFFSET, 0)
        self.logger.debug('Get Screensize: X: {}, Y: {}, X-Offset: {}, Y-Offset: {}', self._screen_x, self._screen_y,
                          x_offset, y_offset)
        # self._resocalc.get_x_y_ratio(self, self._screen_x, self._screen_y, x_offset, y_offset)
        # TODO: Why is there a faulty typecheck here?
        self._resocalc.get_x_y_ratio(self, self._screen_x, self._screen_y, x_offset, y_offset)
