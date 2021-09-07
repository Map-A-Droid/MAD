import asyncio
import math
import time
from abc import ABC, abstractmethod
from typing import Tuple, Optional, Union, Dict

from loguru import logger

from mapadroid.data_handler.AbstractMitmMapper import AbstractMitmMapper
from mapadroid.data_handler.mitm_data.holder.latest_mitm_data.LatestMitmDataEntry import LatestMitmDataEntry
from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.helper.TrsStatusHelper import TrsStatusHelper
from mapadroid.db.model import SettingsArea, TrsStatus, SettingsWalkerarea
from mapadroid.mapping_manager.MappingManager import MappingManager
from mapadroid.mapping_manager.MappingManagerDevicemappingKey import MappingManagerDevicemappingKey
from mapadroid.ocr.pogoWindows import PogoWindows
from mapadroid.ocr.screenPath import WordToScreenMatching
from mapadroid.utils.DatetimeWrapper import DatetimeWrapper
from mapadroid.utils.ProtoIdentifier import ProtoIdentifier
from mapadroid.utils.collections import Location
from mapadroid.utils.geo import get_distance_of_two_points_in_meters
from mapadroid.utils.madConstants import TIMESTAMP_NEVER, FALLBACK_MITM_WAIT_TIMEOUT, \
    MINIMUM_DISTANCE_ALLOWANCE_FOR_GMO, SECONDS_BEFORE_ARRIVAL_OF_WALK_BUFFER
from mapadroid.utils.madGlobals import InternalStopWorkerException, application_args, TransportType, PositionType, \
    WebsocketWorkerRemovedException, FortSearchResultTypes
from mapadroid.websocket.AbstractCommunicator import AbstractCommunicator
from mapadroid.worker.ReceivedTypeEnum import ReceivedType
from mapadroid.worker.WorkerState import WorkerState
from mapadroid.worker.WorkerType import WorkerType
from mapadroid.worker.strategy.AbstractWorkerStrategy import AbstractWorkerStrategy


class AbstractMitmBaseStrategy(AbstractWorkerStrategy, ABC):
    def __init__(self, area_id: int, communicator: AbstractCommunicator,
                 mapping_manager: MappingManager,
                 db_wrapper: DbWrapper, word_to_screen_matching: WordToScreenMatching,
                 pogo_windows_handler: PogoWindows,
                 walker: SettingsWalkerarea,
                 worker_state: WorkerState,
                 mitm_mapper: AbstractMitmMapper):
        super().__init__(area_id=area_id,
                         communicator=communicator, mapping_manager=mapping_manager,
                         db_wrapper=db_wrapper,
                         word_to_screen_matching=word_to_screen_matching,
                         pogo_windows_handler=pogo_windows_handler,
                         walker=walker,
                         worker_state=worker_state)
        self._mitm_mapper: AbstractMitmMapper = mitm_mapper
        # TODO: Consider placement
        self._latest_encounter_update = 0
        self._encounter_ids = {}

    @abstractmethod
    async def _check_for_data_content(self, latest: Dict[str, LatestMitmDataEntry],
                                      proto_to_wait_for: ProtoIdentifier,
                                      timestamp: int) \
            -> Tuple[ReceivedType, Optional[object]]:
        """
        Wait_for_data for each worker
        :return:
        """
        pass

    async def pre_work_loop(self) -> None:
        await self._mitm_mapper.set_injection_status(self._worker_state.origin, False)
        start_position = await self.get_devicesettings_value(MappingManagerDevicemappingKey.STARTCOORDS_OF_WALKER, None)
        calc_type = await self._mapping_manager.routemanager_get_calc_type(self._area_id)
        geofence_helper_of_area = await self._mapping_manager.routemanager_get_geofence_helper(self._area_id)
        if (start_position
                and await self._mapping_manager.routemanager_is_levelmode(self._area_id) and calc_type == "routefree"):
            startcoords = (
                await self.get_devicesettings_value(MappingManagerDevicemappingKey.STARTCOORDS_OF_WALKER)).replace(' ',
                                                                                                                   '') \
                .replace('_', '').split(',')

            if not geofence_helper_of_area.is_coord_inside_include_geofence(Location(
                    float(startcoords[0]), float(startcoords[1]))):
                logger.info("Startcoords not in geofence - setting middle of fence as starting position")
                lat, lng = geofence_helper_of_area.get_middle_from_fence()
                start_position = str(lat) + "," + str(lng)

        if start_position is None and \
                (await self._mapping_manager.routemanager_is_levelmode(self.area_id) and calc_type == "routefree"):
            logger.info("Starting level mode without worker start position")
            # setting coords
            lat, lng = geofence_helper_of_area.get_middle_from_fence()
            start_position = str(lat) + "," + str(lng)

        if start_position is not None:
            startcoords = start_position.replace(' ', '').replace('_', '').split(',')

            if not geofence_helper_of_area.is_coord_inside_include_geofence(Location(
                    float(startcoords[0]), float(startcoords[1]))):
                logger.info("Startcoords not in geofence - setting middle of fence as startposition")
                lat, lng = geofence_helper_of_area.get_middle_from_fence()
                start_position = str(lat) + "," + str(lng)
                startcoords = start_position.replace(' ', '').replace('_', '').split(',')

            logger.info('Setting startcoords or walker lat {} / lng {}', startcoords[0], startcoords[1])
            await self._communicator.set_location(Location(float(startcoords[0]), float(startcoords[1])), 0)
            logger.info("Updating startposition")
            await self._mapping_manager.set_worker_startposition(
                routemanager_id=self._area_id,
                worker_name=self._worker_state.origin,
                lat=float(startcoords[0]),
                lon=float(startcoords[1]))

        logger.info("Worker starting actual work")
        try:
            await self.turn_screen_on_and_start_pogo()
            # register worker  in routemanager
            logger.info("Try to register in Routemanager {}",
                        await self._mapping_manager.routemanager_get_name(self._area_id))
            await self._mapping_manager.register_worker_to_routemanager(self._area_id,
                                                                        self._worker_state.origin)
            await self._update_screen_size()
        except WebsocketWorkerRemovedException:
            logger.error("Timeout during init of worker")
            # no cleanup required here? TODO: signal websocket server somehow
            self._worker_state.stop_worker_event.set()

    async def _wait_for_data(self, timestamp: float = None,
                             proto_to_wait_for: ProtoIdentifier = ProtoIdentifier.GMO, timeout=None) \
            -> Tuple[ReceivedType, Optional[Union[dict, FortSearchResultTypes]]]:
        key = str(proto_to_wait_for.value)
        if timestamp is None:
            timestamp = time.time()
        # Cut off decimal places of timestamp as PD also does that...
        timestamp = int(timestamp)
        if timeout is None:
            timeout = await self.get_devicesettings_value(MappingManagerDevicemappingKey.MITM_WAIT_TIMEOUT,
                                                          FALLBACK_MITM_WAIT_TIMEOUT)
        # let's fetch the latest data to add the offset to timeout (in case device and server times are off...)
        logger.info('Waiting for data after {}',
                    DatetimeWrapper.fromtimestamp(timestamp))
        position_type = await self._mapping_manager.routemanager_get_position_type(self._area_id,
                                                                                   self._worker_state.origin)
        type_of_data_returned = ReceivedType.UNDEFINED
        data = None
        # Any data after timestamp + timeout should be valid!
        last_time_received = TIMESTAMP_NEVER
        logger.debug("Waiting for data ({}) after {} with timeout of {}s.",
                     proto_to_wait_for, DatetimeWrapper.fromtimestamp(timestamp), timeout)
        while not self._worker_state.stop_worker_event.is_set() and int(timestamp + timeout) >= int(time.time()) \
                and last_time_received < timestamp:
            latest: Dict[Union[int, str], LatestMitmDataEntry] = await self \
                ._mitm_mapper.get_full_latest_data(self._worker_state.origin)

            if latest is None:
                logger.info("Nothing received from worker since MAD started")
                await asyncio.sleep(application_args.wait_for_data_sleep_duration)
                continue
            latest_proto_entry: Optional[LatestMitmDataEntry] = latest.get(key, None)
            if not latest_proto_entry:
                logger.info("No data linked to the requested proto since MAD started.")
                await asyncio.sleep(application_args.wait_for_data_sleep_duration)
                continue
            # Not checking the timestamp against the proto awaited in here since custom handling may be adequate.
            # E.g. Questscan may yield errors like clicking mons instead of stops - which we need to detect as well
            latest_location: Optional[Location] = await self._mitm_mapper.get_last_known_location(
                self._worker_state.origin)
            check_data = True
            if (latest_location is None or latest_location.lat == latest_location.lng == 1000
                    or not (latest_location.lat != 0.0 and latest_location.lng != 0.0 and
                            -90.0 <= latest_location.lat <= 90.0 and
                            -180.0 <= latest_location.lng <= 180.0)):
                logger.debug("Data may be valid but does not contain a proper location yet: {}",
                             str(latest_location))
                check_data = False
            elif proto_to_wait_for == ProtoIdentifier.GMO:
                check_data = await self._is_location_within_allowed_range(latest_location)

            if check_data:
                type_of_data_returned, data = await self._check_for_data_content(
                    latest, proto_to_wait_for, timestamp)

            await self.raise_stop_worker_if_applicable()
            if type_of_data_returned == ReceivedType.UNDEFINED:
                # We don't want to sleep if we have received something that may be useful to us...
                # In case last_time_received was set, we reset it after the first
                # iteration to not run into trouble (endless loop)
                last_time_received = TIMESTAMP_NEVER
            else:
                last_time_received = latest_proto_entry.timestamp_of_data_retrieval
                break
            await asyncio.sleep(application_args.wait_for_data_sleep_duration)

        if proto_to_wait_for == ProtoIdentifier.GMO:
            if type_of_data_returned != ReceivedType.UNDEFINED:
                await self._reset_restart_count_and_collect_stats(timestamp,
                                                                  last_time_received,
                                                                  position_type)
            else:
                await self._handle_proto_timeout(timestamp, position_type)

        if type_of_data_returned == ReceivedType.UNDEFINED:
            logger.info("Timeout waiting for useful data. Type requested was {}, received {}",
                        proto_to_wait_for, type_of_data_returned)
        else:
            logger.success("Got data of type {}", type_of_data_returned)

        loop = asyncio.get_running_loop()
        loop.create_task(self.worker_stats())
        # TODO: Rather freeze the state that is to be submitted and pass it to another task for performance reasons
        # await self.worker_stats()
        return type_of_data_returned, data

    async def raise_stop_worker_if_applicable(self):
        """
        Checks if the worker is supposed to be stopped or the routemanagers/mappings have changed
        Raises: InternalStopWorkerException
        """
        if not await self._mapping_manager.routemanager_present(self._area_id) \
                or self._worker_state.stop_worker_event.is_set():
            logger.error("killed while sleeping")
            raise InternalStopWorkerException
        position_type = await self._mapping_manager.routemanager_get_position_type(self._area_id,
                                                                                   self._worker_state.origin)
        if position_type is None:
            logger.info("Mappings/Routemanagers have changed, stopping worker to be created again")
            raise InternalStopWorkerException

    async def _is_location_within_allowed_range(self, latest_location):
        logger.debug2("Checking (data) location reported by {} at {} against real data location {}",
                      self._worker_state.origin,
                      self._worker_state.current_location,
                      latest_location)
        distance_to_data = get_distance_of_two_points_in_meters(float(latest_location.lat),
                                                                float(latest_location.lng),
                                                                float(self._worker_state.current_location.lat),
                                                                float(self._worker_state.current_location.lng))
        max_distance_of_mode = await self._mapping_manager.routemanager_get_max_radius(self._area_id)
        max_distance_for_worker = application_args.maximum_valid_distance
        if max_distance_for_worker > max_distance_of_mode > MINIMUM_DISTANCE_ALLOWANCE_FOR_GMO:
            # some modes may be too strict (e.g. quests with 0.0001m calculations for routes)
            # yet, the route may "require" a stricter ruling than max valid distance
            max_distance_for_worker = max_distance_of_mode
        logger.debug2("Distance of worker {} to (data) location: {}", self._worker_state.origin, distance_to_data)
        if distance_to_data > max_distance_for_worker:
            logger.debug("Location too far from worker position, max distance allowed: {}m",
                         max_distance_for_worker)
        return distance_to_data <= max_distance_for_worker

    async def _walk_to_location(self, speed: float) -> int:
        """
        Calls the communicator to walk from self.last_location to self.current_location at the speed passed as an arg
        Args:
            speed:

        Returns:

        """
        self._worker_state.last_transport_type = TransportType.WALK
        time_before_walk = math.floor(time.time())
        await self._communicator.walk_from_to(self._worker_state.last_location, self._worker_state.current_location,
                                              speed)
        # We need to roughly estimate when data could have been available, just picking half way for now, distance
        # check should do the rest...
        delay_used = math.floor(time.time())
        if delay_used - SECONDS_BEFORE_ARRIVAL_OF_WALK_BUFFER < time_before_walk:
            # duration of walk was rather short, let's go with that...
            delay_used = time_before_walk
        elif (math.floor((math.floor(time.time()) + time_before_walk) / 2) <
              delay_used - SECONDS_BEFORE_ARRIVAL_OF_WALK_BUFFER):
            # half way through the walk was earlier than 10s in the past, just gonna go with magic numbers once more
            delay_used -= SECONDS_BEFORE_ARRIVAL_OF_WALK_BUFFER
        else:
            # half way through was within the last 10s, we can use that to check for data afterwards
            delay_used = math.floor((math.floor(time.time()) + time_before_walk) / 2)
        return delay_used

    async def _get_route_manager_settings_and_distance_to_current_location(self) -> Tuple[float, SettingsArea]:
        if not await self._mapping_manager.routemanager_present(self._area_id) \
                or self._worker_state.stop_worker_event.is_set():
            raise InternalStopWorkerException
        routemanager_settings = await self._mapping_manager.routemanager_get_settings(self._area_id)
        distance = get_distance_of_two_points_in_meters(float(self._worker_state.last_location.lat),
                                                        float(
                                                            self._worker_state.last_location.lng),
                                                        float(
                                                            self._worker_state.current_location.lat),
                                                        float(self._worker_state.current_location.lng))
        logger.debug('Moving {} meters to the next position', round(distance, 2))
        return distance, routemanager_settings

    async def _handle_proto_timeout(self, fix_ts: int,
                                    position_type: PositionType):
        now_ts: int = int(time.time())
        routemanager_settings = await self._mapping_manager.routemanager_get_settings(self._area_id)
        worker_type: WorkerType = WorkerType(routemanager_settings.mode)

        await self._mitm_mapper.stats_collect_location_data(self._worker_state.origin,
                                                            self._worker_state.current_location, False,
                                                            fix_ts,
                                                            position_type,
                                                            TIMESTAMP_NEVER,
                                                            worker_type, self._worker_state.last_transport_type,
                                                            now_ts)

        self._worker_state.restart_count += 1
        restart_thresh = await self.get_devicesettings_value(MappingManagerDevicemappingKey.RESTART_THRESH, 5)
        reboot_thresh = await self.get_devicesettings_value(MappingManagerDevicemappingKey.REBOOT_THRESH, 3)
        if await self._mapping_manager.routemanager_get_route_stats(self._area_id,
                                                                    self._worker_state.origin) is not None:
            if await self._mapping_manager.routemanager_get_init(self._area_id):
                restart_thresh = restart_thresh * 2
                reboot_thresh = reboot_thresh * 2
        if self._worker_state.restart_count > restart_thresh:
            self._worker_state.reboot_count += 1
            if self._worker_state.reboot_count > reboot_thresh \
                    and await self.get_devicesettings_value(MappingManagerDevicemappingKey.REBOOT, True):
                logger.warning("Too many timeouts - Rebooting device")
                await self._reboot(mitm_mapper=self._mitm_mapper)
                raise InternalStopWorkerException

            # self._mitm_mapper.
            self._worker_state.restart_count = 0
            logger.warning("Too many timeouts - Restarting game")
            await self._restart_pogo(True, self._mitm_mapper)

    async def stop_pogo(self):
        stopped: bool = await super().stop_pogo()
        if stopped:
            await self._mitm_mapper.set_injection_status(self._worker_state.origin, False)

    async def worker_stats(self):
        logger.debug('===============================')
        logger.debug('Worker Stats')
        logger.debug('Origin: {} [{}]', self._worker_state.origin, self._worker_state.device_id)
        logger.debug('Routemanager: {}', self._area_id)
        logger.debug('Restart Counter: {}', self._worker_state.restart_count)
        logger.debug('Reboot Counter: {}', self._worker_state.reboot_count)
        logger.debug('Reboot Option: {}',
                     await self.get_devicesettings_value(MappingManagerDevicemappingKey.REBOOT, True))
        logger.debug('Current Pos: {} {}', self._worker_state.current_location.lat,
                     self._worker_state.current_location.lng)
        logger.debug('Last Pos: {} {}', self._worker_state.last_location.lat, self._worker_state.last_location.lng)
        routemanager_status = await self._mapping_manager.routemanager_get_route_stats(self._area_id,
                                                                                       self._worker_state.origin)
        if routemanager_status is None:
            logger.warning("Routemanager of {} not available to update stats", self._worker_state.origin)
            routemanager_status = [None, None]
        else:
            logger.debug('Route Pos: {} - Route Length: {}', routemanager_status[0], routemanager_status[1])
        routemanager_init: bool = await self._mapping_manager.routemanager_get_init(self._area_id)
        logger.debug('Init Mode: {}', routemanager_init)
        logger.debug('Last Date/Time of Data: {}', self._worker_state.last_received_data_time)
        logger.debug('===============================')
        async with self._db_wrapper as session, session:
            status: Optional[TrsStatus] = await TrsStatusHelper.get(session, self._worker_state.device_id)
            if not status:
                status = TrsStatus()
                status.device_id = self._worker_state.device_id
            status.currentPos = (self._worker_state.current_location.lat, self._worker_state.current_location.lng)
            status.lastPos = (self._worker_state.last_location.lat, self._worker_state.last_location.lng)
            status.routePos = routemanager_status[0]
            status.routeMax = routemanager_status[1]
            status.area_id = self._area_id
            status.rebootCounter = self._worker_state.reboot_count
            status.init = routemanager_init
            status.rebootingOption = await self.get_devicesettings_value(MappingManagerDevicemappingKey.REBOOT, True)
            status.restartCounter = self._worker_state.restart_count
            status.currentSleepTime = self._worker_state.current_sleep_duration

            if self._worker_state.last_received_data_time:
                status.lastProtoDateTime = DatetimeWrapper.now()
                self._worker_state.last_received_data_time = None
            session.add(status)
            try:
                await session.commit()
            except Exception as e:
                logger.warning("Failed saving status of worker {}: {}", self._worker_state.origin, e)

    async def _reset_restart_count_and_collect_stats(self, fix_ts: int, timestamp_received_raw: int,
                                                     position_type: PositionType):
        logger.success('Received data')
        self._worker_state.reboot_count = 0
        self._worker_state.restart_count = 0
        self._worker_state.last_received_data_time = DatetimeWrapper.now()
        # TODO: Fire and forget async?
        now_ts: int = int(time.time())
        routemanager_settings = await self._mapping_manager.routemanager_get_settings(self._area_id)
        worker_type: WorkerType = WorkerType(routemanager_settings.mode)

        await self._mitm_mapper.stats_collect_location_data(self._worker_state.origin,
                                                            self._worker_state.current_location, True,
                                                            fix_ts,
                                                            position_type, timestamp_received_raw,
                                                            worker_type, self._worker_state.last_transport_type,
                                                            now_ts)

    async def start_pogo(self) -> bool:
        started_pogo: bool = await super().start_pogo()
        if not await self._wait_for_injection() or self._worker_state.stop_worker_event.is_set():
            await self._mitm_mapper.set_injection_status(self._worker_state.origin, False)
            raise InternalStopWorkerException
        else:
            return started_pogo

    async def _wait_for_injection(self):
        not_injected_count = 0
        injection_thresh_reboot = int(
            await self.get_devicesettings_value(MappingManagerDevicemappingKey.INJECTION_THRESH_REBOOT, 20))
        # TODO: Else check MitmApp was started...
        window_check_frequency = 3
        while not await self._mitm_mapper.get_injection_status(self._worker_state.origin):
            await self._check_for_mad_job()
            if not_injected_count >= injection_thresh_reboot:
                logger.warning("Not injected in time - reboot")
                await self._reboot(self._mitm_mapper)
                return False
            logger.info("Didn't receive any data yet. (Retry count: {}/{})", not_injected_count,
                        injection_thresh_reboot)
            if (not_injected_count != 0 and not_injected_count % window_check_frequency == 0) \
                    and not self._worker_state.stop_worker_event.is_set():
                logger.info("Retry check_windows while waiting for injection at count {}",
                            not_injected_count)
                await self._handle_screen()
            not_injected_count += 1
            wait_time = 0
            while wait_time < 20:
                wait_time += 1
                if self._worker_state.stop_worker_event.is_set():
                    logger.error("Killed while waiting for injection")
                    return False
                await asyncio.sleep(1)
        return True

    @staticmethod
    def _gmo_cells_contain_multiple_of_key(gmo: dict, key_in_cell: str) -> bool:
        if not gmo or not key_in_cell or "cells" not in gmo:
            return False
        cells = gmo.get("cells", [])
        if not cells or not isinstance(cells, list):
            return False
        amount_of_key: int = 0
        for cell in cells:
            value_of_key = cell.get(key_in_cell, None)
            if value_of_key and isinstance(value_of_key, list):
                amount_of_key += len(value_of_key)
        return amount_of_key > 0

    async def _additional_health_check(self) -> None:
        # Ensure PogoDroid was started...
        await self._communicator.passthrough("su -c 'am startservice -n com.mad.pogodroid/.services.HookReceiverService'")
