import asyncio
import math
import time
from abc import abstractmethod, ABC
from asyncio import Task
from datetime import datetime
from enum import Enum
from typing import Dict, Optional, Tuple, Union

from loguru import logger

from mapadroid.data_handler.MitmMapper import MitmMapper
from mapadroid.data_handler.mitm_data.holder.latest_mitm_data.LatestMitmDataEntry import LatestMitmDataEntry
from mapadroid.db.helper.TrsStatusHelper import TrsStatusHelper
from mapadroid.db.model import SettingsArea, TrsStatus
from mapadroid.mapping_manager import MappingManager
from mapadroid.mapping_manager.MappingManagerDevicemappingKey import MappingManagerDevicemappingKey
from mapadroid.ocr.pogoWindows import PogoWindows
from mapadroid.utils.ProtoIdentifier import ProtoIdentifier
from mapadroid.utils.collections import Location
from mapadroid.utils.geo import (get_distance_of_two_points_in_meters,
                                 get_lat_lng_offsets_by_distance)
from mapadroid.utils.madGlobals import InternalStopWorkerException, PositionType, TransportType
from mapadroid.websocket.AbstractCommunicator import AbstractCommunicator
from mapadroid.worker.WorkerBase import FortSearchResultTypes, WorkerBase

WALK_AFTER_TELEPORT_SPEED = 11
FALLBACK_MITM_WAIT_TIMEOUT = 45
TIMESTAMP_NEVER = 0
WAIT_FOR_DATA_NEXT_ROUND_SLEEP = 0.5
# Distance in meters that are to be allowed to consider a GMO as within a valid range
# Some modes calculate with extremely strict distances (0.0001m for example), thus not allowing
# direct use of routemanager radius as a distance (which would allow long distances for raid scans as well)
MINIMUM_DISTANCE_ALLOWANCE_FOR_GMO = 5

# Since GMOs may arrive during walks, we define sort of a buffer to use.
# That buffer can be subtracted in case a walk was longer than that buffer.
SECONDS_BEFORE_ARRIVAL_OF_WALK_BUFFER = 10


class LatestReceivedType(Enum):
    UNDEFINED = -1
    GYM = 0
    STOP = 2
    MON = 3
    CLEAR = 4
    GMO = 5
    FORT_SEARCH_RESULT = 6


class MITMBase(WorkerBase, ABC):
    def __init__(self, args, dev_id, origin, last_known_state, communicator: AbstractCommunicator,
                 mapping_manager: MappingManager,
                 area_id: int, routemanager_id: int, db_wrapper, mitm_mapper: MitmMapper,
                 pogo_window_manager: PogoWindows,
                 walker: Dict = None, event=None):
        WorkerBase.__init__(self, args, dev_id, origin, last_known_state, communicator,
                            mapping_manager=mapping_manager, area_id=area_id,
                            routemanager_id=routemanager_id,
                            db_wrapper=db_wrapper,
                            pogo_window_manager=pogo_window_manager, walker=walker, event=event)
        self._reboot_count = 0
        self._restart_count = 0
        self._rec_data_time = ""
        self._mitm_mapper = mitm_mapper
        self._latest_encounter_update = 0
        self._encounter_ids = {}
        self._current_sleep_time = 0
        self._clear_quests_failcount = 0
        self._enhanced_mode = False
        self._dev_id = dev_id

    async def start_worker(self) -> Task:
        async with self._db_wrapper as session, session:
            await TrsStatusHelper.save_idle_status(session, self._db_wrapper.get_instance_id(),
                                                   self._dev_id, 0)
            await session.commit()

        now_ts: int = int(time.time())
        await self._mitm_mapper.stats_collect_location_data(self._origin, self.current_location, True,
                                                            now_ts,
                                                            PositionType.STARTUP,
                                                            TIMESTAMP_NEVER,
                                                            self._walker.name, self._transporttype,
                                                            now_ts)

        self._enhanced_mode = await self.get_devicesettings_value(MappingManagerDevicemappingKey.ENHANCED_MODE_QUEST,
                                                                  False)
        return await super().start_worker()

    async def _walk_after_teleport(self, walk_distance_post_teleport) -> float:
        """
        Args:
            walk_distance_post_teleport:

        Returns:
            Distance walked in one way
        """
        lat_offset, lng_offset = get_lat_lng_offsets_by_distance(walk_distance_post_teleport)
        to_walk = get_distance_of_two_points_in_meters(float(self.current_location.lat),
                                                       float(
                                                           self.current_location.lng),
                                                       float(
                                                           self.current_location.lat) + lat_offset,
                                                       float(self.current_location.lng) + lng_offset)
        logger.info("Walking roughly: {:.2f}m", to_walk)
        await asyncio.sleep(0.3)
        await self._communicator.walk_from_to(self.current_location,
                                              Location(self.current_location.lat + lat_offset,
                                                       self.current_location.lng + lng_offset),
                                              WALK_AFTER_TELEPORT_SPEED)
        logger.debug("Walking back")
        await asyncio.sleep(0.3)
        await self._communicator.walk_from_to(Location(self.current_location.lat + lat_offset,
                                                       self.current_location.lng + lng_offset),
                                              self.current_location,
                                              WALK_AFTER_TELEPORT_SPEED)
        logger.debug("Done walking")
        return to_walk

    async def _wait_for_data(self, timestamp: float = None,
                             proto_to_wait_for: ProtoIdentifier = ProtoIdentifier.GMO, timeout=None) \
            -> Tuple[LatestReceivedType, Optional[Union[dict, FortSearchResultTypes]]]:
        if timestamp is None:
            timestamp = time.time()
        # Cut off decimal places of timestamp as PD also does that...
        timestamp = int(timestamp)
        if timeout is None:
            timeout = await self.get_devicesettings_value(MappingManagerDevicemappingKey.MITM_WAIT_TIMEOUT,
                                                          FALLBACK_MITM_WAIT_TIMEOUT)
        # let's fetch the latest data to add the offset to timeout (in case device and server times are off...)
        logger.info('Waiting for data after {}',
                    datetime.fromtimestamp(timestamp))
        position_type = await self._mapping_manager.routemanager_get_position_type(self._routemanager_id,
                                                                                   self._origin)
        type_of_data_returned = LatestReceivedType.UNDEFINED
        data = None
        # Any data after timestamp + timeout should be valid!
        last_time_received = TIMESTAMP_NEVER
        logger.debug("Waiting for data ({}) after {} with timeout of {}s.",
                     proto_to_wait_for, datetime.fromtimestamp(timestamp), timeout)
        while not self._stop_worker_event.is_set() and int(timestamp + timeout) >= int(time.time()) \
                and last_time_received < timestamp:
            latest: Dict[Union[int, str], LatestMitmDataEntry] = await self\
                ._mitm_mapper.get_full_latest_data(self._origin)

            if latest is None:
                logger.info("Nothing received from worker since MAD started")
                await asyncio.sleep(WAIT_FOR_DATA_NEXT_ROUND_SLEEP)
                continue
            latest_proto_entry: Optional[LatestMitmDataEntry] = latest.get(proto_to_wait_for.value, None)
            if not latest_proto_entry:
                logger.info("No data linked to the requested proto since MAD started.")
                await asyncio.sleep(WAIT_FOR_DATA_NEXT_ROUND_SLEEP)
                continue
            # Not checking the timestamp against the proto awaited in here since custom handling may be adequate.
            # E.g. Questscan may yield errors like clicking mons instead of stops - which we need to detect as well
            latest_location: Optional[Location] = await self._mitm_mapper.get_last_known_location(self._origin)
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
            if type_of_data_returned == LatestReceivedType.UNDEFINED:
                # We don't want to sleep if we have received something that may be useful to us...
                await asyncio.sleep(WAIT_FOR_DATA_NEXT_ROUND_SLEEP)
                # In case last_time_received was set, we reset it after the first
                # iteration to not run into trouble (endless loop)
                last_time_received = TIMESTAMP_NEVER
            else:
                last_time_received = latest_proto_entry.timestamp_of_data_retrieval
                break

        if type_of_data_returned != LatestReceivedType.UNDEFINED:
            await self._reset_restart_count_and_collect_stats(timestamp,
                                                              last_time_received,
                                                              position_type)
        else:
            await self._handle_proto_timeout(timestamp, position_type, proto_to_wait_for,
                                             type_of_data_returned)

        loop = asyncio.get_running_loop()
        loop.create_task(self.worker_stats())
        # TODO: Rather freeze the state that is to be submitted and pass it to another task for performance reasons
        # await self.worker_stats()
        return type_of_data_returned, data

    async def _handle_proto_timeout(self, fix_ts: int,
                                    position_type: PositionType, proto_to_wait_for: ProtoIdentifier,
                                    type_of_data_returned):
        logger.info("Timeout waiting for useful data. Type requested was {}, received {}",
                    proto_to_wait_for, type_of_data_returned)
        now_ts: int = int(time.time())
        await self._mitm_mapper.stats_collect_location_data(self._origin, self.current_location, False,
                                                            fix_ts,
                                                            position_type,
                                                            TIMESTAMP_NEVER,
                                                            self._walker.name, self._transporttype,
                                                            now_ts)

        self._restart_count += 1
        restart_thresh = await self.get_devicesettings_value(MappingManagerDevicemappingKey.RESTART_THRESH, 5)
        reboot_thresh = await self.get_devicesettings_value(MappingManagerDevicemappingKey.REBOOT_THRESH, 3)
        if await self._mapping_manager.routemanager_get_route_stats(self._routemanager_id,
                                                                    self._origin) is not None:
            if self._init:
                restart_thresh = restart_thresh * 2
                reboot_thresh = reboot_thresh * 2
        if self._restart_count > restart_thresh:
            self._reboot_count += 1
            if self._reboot_count > reboot_thresh \
                    and self.get_devicesettings_value(MappingManagerDevicemappingKey.REBOOT, True):
                logger.warning("Too many timeouts - Rebooting device")
                await self._reboot(mitm_mapper=self._mitm_mapper)
                raise InternalStopWorkerException

            # self._mitm_mapper.
            self._restart_count = 0
            logger.warning("Too many timeouts - Restarting game")
            await self._restart_pogo(True, self._mitm_mapper)

    async def _reset_restart_count_and_collect_stats(self, fix_ts: int, timestamp_received_raw: int,
                                                     position_type: PositionType):
        logger.success('Received data')
        self._reboot_count = 0
        self._restart_count = 0
        self._rec_data_time = datetime.now()
        # TODO: Fire and forget async?
        now_ts: int = int(time.time())
        await self._mitm_mapper.stats_collect_location_data(self._origin, self.current_location, True,
                                                            fix_ts,
                                                            position_type, timestamp_received_raw,
                                                            self._walker.name, self._transporttype,
                                                            now_ts)

    async def raise_stop_worker_if_applicable(self):
        """
        Checks if the worker is supposed to be stopped or the routemanagers/mappings have changed
        Raises: InternalStopWorkerException
        """
        if not await self._mapping_manager.routemanager_present(self._routemanager_id) \
                or self._stop_worker_event.is_set():
            logger.error("killed while sleeping")
            raise InternalStopWorkerException
        position_type = await self._mapping_manager.routemanager_get_position_type(self._routemanager_id,
                                                                                   self._origin)
        if position_type is None:
            logger.info("Mappings/Routemanagers have changed, stopping worker to be created again")
            raise InternalStopWorkerException

    async def _is_location_within_allowed_range(self, latest_location):
        logger.debug2("Checking (data) location reported by {} at {} against real data location {}",
                      self._origin,
                      self.current_location,
                      latest_location)
        distance_to_data = get_distance_of_two_points_in_meters(float(latest_location.lat),
                                                                float(latest_location.lng),
                                                                float(self.current_location.lat),
                                                                float(self.current_location.lng))
        max_distance_of_mode = await self._mapping_manager.routemanager_get_max_radius(self._routemanager_id)
        max_distance_for_worker = self._applicationArgs.maximum_valid_distance
        if max_distance_for_worker > max_distance_of_mode > MINIMUM_DISTANCE_ALLOWANCE_FOR_GMO:
            # some modes may be too strict (e.g. quests with 0.0001m calculations for routes)
            # yet, the route may "require" a stricter ruling than max valid distance
            max_distance_for_worker = max_distance_of_mode
        logger.debug2("Distance of worker {} to (data) location: {}", self._origin, distance_to_data)
        if distance_to_data > max_distance_for_worker:
            logger.debug("Location too far from worker position, max distance allowed: {}m",
                         max_distance_for_worker)
        return distance_to_data <= max_distance_for_worker

    async def _start_pogo(self) -> bool:
        if await self._communicator.is_pogo_topmost():
            return True
        await self._mitm_mapper.set_injection_status(self._origin, False)
        started_pogo: bool = await super()._start_pogo()
        if not await self._wait_for_injection() or self._stop_worker_event.is_set():
            raise InternalStopWorkerException
        else:
            return started_pogo

    async def _wait_for_injection(self):
        self._not_injected_count = 0
        reboot = await self.get_devicesettings_value(MappingManagerDevicemappingKey.REBOOT, True)
        injection_thresh_reboot = 'Unlimited'
        if reboot:
            injection_thresh_reboot = int(
                await self.get_devicesettings_value(MappingManagerDevicemappingKey.INJECTION_THRESH_REBOOT, 20))
        window_check_frequency = 3
        while not await self._mitm_mapper.get_injection_status(self._origin):
            await self._check_for_mad_job()
            if reboot and self._not_injected_count >= injection_thresh_reboot:
                logger.warning("Not injected in time - reboot")
                await self._reboot(self._mitm_mapper)
                return False
            logger.info("Didn't receive any data yet. (Retry count: {}/{})", self._not_injected_count,
                        injection_thresh_reboot)
            if (self._not_injected_count != 0 and self._not_injected_count % window_check_frequency == 0) \
                    and not self._stop_worker_event.is_set():
                logger.info("Retry check_windows while waiting for injection at count {}",
                            self._not_injected_count)
                await self._ensure_pogo_topmost()
            self._not_injected_count += 1
            wait_time = 0
            while wait_time < 20:
                wait_time += 1
                if self._stop_worker_event.is_set():
                    logger.error("Killed while waiting for injection")
                    return False
                await asyncio.sleep(1)
        return True

    @abstractmethod
    async def _check_for_data_content(self, latest, proto_to_wait_for: ProtoIdentifier, timestamp) \
            -> Tuple[LatestReceivedType, Optional[object]]:
        """
        Wait_for_data for each worker
        :return:
        """
        pass

    async def _walk_to_location(self, speed: float) -> int:
        """
        Calls the communicator to walk from self.last_location to self.current_location at the speed passed as an arg
        Args:
            speed:

        Returns:

        """
        self._transporttype = TransportType.WALK
        time_before_walk = math.floor(time.time())
        await self._communicator.walk_from_to(self.last_location, self.current_location, speed)
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
        if not await self._mapping_manager.routemanager_present(self._routemanager_id) \
                or self._stop_worker_event.is_set():
            raise InternalStopWorkerException
        routemanager_settings = await self._mapping_manager.routemanager_get_settings(self._routemanager_id)
        distance = get_distance_of_two_points_in_meters(float(self.last_location.lat),
                                                        float(
                                                            self.last_location.lng),
                                                        float(
                                                            self.current_location.lat),
                                                        float(self.current_location.lng))
        logger.debug('Moving {} meters to the next position', round(distance, 2))
        return distance, routemanager_settings

    async def _clear_quests(self, delayadd, openmenu=True):
        logger.debug('{_clear_quests} called')
        if openmenu:
            x, y = self._resocalc.get_coords_quest_menu(self)
            await self._communicator.click(int(x), int(y))
            logger.debug("_clear_quests Open menu: {}, {}", int(x), int(y))
            await asyncio.sleep(6 + int(delayadd))

        x, y = self._resocalc.get_close_main_button_coords(self)
        await self._communicator.click(int(x), int(y))
        await asyncio.sleep(1.5)
        logger.debug('{_clear_quests} finished')

    async def _click_pokestop_at_current_location(self, delayadd):
        logger.debug('{_open_gym} called')
        await asyncio.sleep(.5)
        x, y = self._resocalc.get_gym_click_coords(self)
        await self._communicator.click(int(x), int(y))
        await asyncio.sleep(.5 + int(delayadd))
        logger.debug('{_open_gym} finished')

    async def _close_gym(self, delayadd):
        logger.debug('{_close_gym} called')
        x, y = self._resocalc.get_close_main_button_coords(self)
        await self._communicator.click(int(x), int(y))
        await asyncio.sleep(1 + int(delayadd))
        logger.debug('{_close_gym} called')

    async def _turn_map(self, delayadd):
        logger.debug('{_turn_map} called')
        logger.info('Turning map')
        x1, x2, y = self._resocalc.get_gym_spin_coords(self)
        await self._communicator.swipe(int(x1), int(y), int(x2), int(y))
        await asyncio.sleep(int(delayadd))
        logger.debug('{_turn_map} called')

    async def worker_stats(self):
        logger.debug('===============================')
        logger.debug('Worker Stats')
        logger.debug('Origin: {} [{}]', self._origin, self._dev_id)
        logger.debug('Routemanager: {} [{}]', self._routemanager_id, self._area_id)
        logger.debug('Restart Counter: {}', self._restart_count)
        logger.debug('Reboot Counter: {}', self._reboot_count)
        logger.debug('Reboot Option: {}',
                     await self.get_devicesettings_value(MappingManagerDevicemappingKey.REBOOT, True))
        logger.debug('Current Pos: {} {}', self.current_location.lat, self.current_location.lng)
        logger.debug('Last Pos: {} {}', self.last_location.lat, self.last_location.lng)
        routemanager_status = await self._mapping_manager.routemanager_get_route_stats(self._routemanager_id,
                                                                                       self._origin)
        if routemanager_status is None:
            logger.warning("Routemanager of {} not available to update stats", self._origin)
            routemanager_status = [None, None]
        else:
            logger.debug('Route Pos: {} - Route Length: {}', routemanager_status[0], routemanager_status[1])
        routemanager_init: bool = await self._mapping_manager.routemanager_get_init(self._routemanager_id)
        logger.debug('Init Mode: {}', routemanager_init)
        logger.debug('Last Date/Time of Data: {}', self._rec_data_time)
        logger.debug('===============================')
        async with self._db_wrapper as session, session:
            status: Optional[TrsStatus] = await TrsStatusHelper.get(session, self._dev_id)
            if not status:
                status = TrsStatus()
                status.device_id = self._dev_id
            status.currentPos = (self.current_location.lat, self.current_location.lng)
            status.lastPos = (self.last_location.lat, self.last_location.lng)
            # status.currentPos = 'POINT(%s,%s)' % (self.current_location.lat, self.current_location.lng)
            # status.lastPos = 'POINT(%s,%s)' % (self.last_location.lat, self.last_location.lng)
            status.routePos = routemanager_status[0]
            status.routeMax = routemanager_status[1]
            status.area_id = self._area_id
            status.rebootCounter = self._reboot_count
            status.init = routemanager_init
            status.rebootingOption = await self.get_devicesettings_value(MappingManagerDevicemappingKey.REBOOT, True)
            status.restartCounter = self._restart_count
            status.currentSleepTime = self._current_sleep_time

            if self._rec_data_time:
                status.lastProtoDateTime = datetime.utcnow()
                self._rec_data_time = None
            session.add(status)
            await session.commit()

    async def _worker_specific_setup_stop(self):
        logger.info("Stopping pogodroid")
        return await self._communicator.stop_app("com.mad.pogodroid")

    async def _worker_specific_setup_start(self):
        logger.info("Starting pogodroid")
        start_result = await self._communicator.start_app("com.mad.pogodroid")
        await asyncio.sleep(5)
        # won't work if PogoDroid is repackaged!
        await self._communicator.passthrough("am startservice com.mad.pogodroid/.services.HookReceiverService")
        return start_result

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
