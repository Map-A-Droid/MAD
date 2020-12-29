import collections
import math
import time
from abc import abstractmethod
from datetime import datetime
from enum import Enum
from typing import Optional, Tuple, Union

from mapadroid.mitm_receiver.MitmMapper import MitmMapper
from mapadroid.ocr.pogoWindows import PogoWindows
from mapadroid.utils import MappingManager
from mapadroid.utils.geo import (get_distance_of_two_points_in_meters,
                                 get_lat_lng_offsets_by_distance)
from mapadroid.utils.logging import LoggerEnums, get_logger
from mapadroid.utils.madGlobals import InternalStopWorkerException
from mapadroid.utils.ProtoIdentifier import ProtoIdentifier
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

logger = get_logger(LoggerEnums.worker)
Location = collections.namedtuple('Location', ['lat', 'lng'])


class LatestReceivedType(Enum):
    UNDEFINED = -1
    GYM = 0
    STOP = 2
    MON = 3
    CLEAR = 4
    GMO = 5
    FORT_SEARCH_RESULT = 6


class MITMBase(WorkerBase):
    def __init__(self, args, dev_id, origin, last_known_state, communicator: AbstractCommunicator,
                 mapping_manager: MappingManager,
                 area_id: int, routemanager_name: str, db_wrapper, mitm_mapper: MitmMapper,
                 pogo_window_manager: PogoWindows,
                 walker=None, event=None):
        WorkerBase.__init__(self, args, dev_id, origin, last_known_state, communicator,
                            mapping_manager=mapping_manager, area_id=area_id,
                            routemanager_name=routemanager_name,
                            db_wrapper=db_wrapper,
                            pogo_window_manager=pogo_window_manager, walker=walker, event=event)
        self._reboot_count = 0
        self._restart_count = 0
        self._rec_data_time = ""
        self._mitm_mapper = mitm_mapper
        self._latest_encounter_update = 0
        self._encounter_ids = {}
        self._current_sleep_time = 0
        self._db_wrapper.save_idle_status(dev_id, False)
        self._clear_quests_failcount = 0
        self._mitm_mapper.collect_location_stats(self._origin, self.current_location, 1, time.time(), 2, 0,
                                                 self._mapping_manager.routemanager_get_mode(
                                                     self._routemanager_name),
                                                 99)
        self._enhanced_mode = self.get_devicesettings_value('enhanced_mode_quest', False)

    def _walk_after_teleport(self, walk_distance_post_teleport) -> float:
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
        self.logger.info("Walking roughly: {:.2f}m", to_walk)
        time.sleep(0.3)
        self._communicator.walk_from_to(self.current_location,
                                        Location(self.current_location.lat + lat_offset,
                                                 self.current_location.lng + lng_offset),
                                        WALK_AFTER_TELEPORT_SPEED)
        self.logger.debug("Walking back")
        time.sleep(0.3)
        self._communicator.walk_from_to(Location(self.current_location.lat + lat_offset,
                                                 self.current_location.lng + lng_offset),
                                        self.current_location,
                                        WALK_AFTER_TELEPORT_SPEED)
        self.logger.debug("Done walking")
        return to_walk

    def _wait_for_data(self, timestamp: float = None,
                       proto_to_wait_for: ProtoIdentifier = ProtoIdentifier.GMO, timeout=None) \
            -> Tuple[LatestReceivedType, Optional[Union[dict, FortSearchResultTypes]]]:
        if timestamp is None:
            timestamp = time.time()
        if timeout is None:
            timeout = self.get_devicesettings_value("mitm_wait_timeout", FALLBACK_MITM_WAIT_TIMEOUT)

        # let's fetch the latest data to add the offset to timeout (in case device and server times are off...)
        self.logger.info('Waiting for data after {}',
                         datetime.fromtimestamp(timestamp))
        position_type = self._mapping_manager.routemanager_get_position_type(self._routemanager_name,
                                                                             self._origin)
        type_of_data_returned = LatestReceivedType.UNDEFINED
        data = None
        latest = self._mitm_mapper.request_latest(self._origin)

        # Any data after timestamp + timeout should be valid!
        last_time_received = TIMESTAMP_NEVER
        if latest is None:
            self.logger.debug("Nothing received from worker since MAD started")
        else:
            latest_proto_entry = latest.get(proto_to_wait_for.value, None)
            if not latest_proto_entry:
                self.logger.debug("No data linked to the requested proto since MAD started.")
            else:
                last_time_received = latest_proto_entry.get("timestamp", TIMESTAMP_NEVER)
        self.logger.debug("Waiting for data ({}) after {} with timeout of {}s. "
                          "Last received timestamp of that type was: {}",
                          proto_to_wait_for, datetime.fromtimestamp(timestamp), timeout,
                          datetime.fromtimestamp(timestamp) if last_time_received != TIMESTAMP_NEVER else "never")
        while type_of_data_returned == LatestReceivedType.UNDEFINED and \
                (int(timestamp + timeout) >= int(time.time()) or last_time_received >= timestamp) \
                and not self._stop_worker_event.is_set():
            latest = self._mitm_mapper.request_latest(self._origin)

            if latest is None:
                self.logger.info("Nothing received from worker since MAD started")
                time.sleep(WAIT_FOR_DATA_NEXT_ROUND_SLEEP)
                continue
            latest_proto_entry = latest.get(proto_to_wait_for.value, None)
            if not latest_proto_entry:
                self.logger.info("No data linked to the requested proto since MAD started.")
                time.sleep(WAIT_FOR_DATA_NEXT_ROUND_SLEEP)
                continue
            # Not checking the timestamp against the proto awaited in here since custom handling may be adequate.
            # E.g. Questscan may yield errors like clicking mons instead of stops - which we need to detect as well
            latest_location: Optional[Location] = latest.get("location", None)
            check_data = True
            if (latest_location is None or latest_location.lat == latest_location.lng == 1000
                    or not (latest_location.lat != 0.0 and latest_location.lng != 0.0 and
                            -90.0 <= latest_location.lat <= 90.0 and
                            -180.0 <= latest_location.lng <= 180.0)):
                self.logger.debug("Data may be valid but does not contain a proper location yet: {}",
                                  str(latest_location))
                check_data = False
            elif proto_to_wait_for == ProtoIdentifier.GMO:
                check_data = self._is_location_within_allowed_range(latest_location)

            if check_data:
                type_of_data_returned, data = self._check_for_data_content(
                    latest, proto_to_wait_for, timestamp)

            self.raise_stop_worker_if_applicable()
            if type_of_data_returned == LatestReceivedType.UNDEFINED:
                # We don't want to sleep if we have received something that may be useful to us...
                time.sleep(WAIT_FOR_DATA_NEXT_ROUND_SLEEP)
            # In case last_time_received was set, we reset it after the first
            # iteration to not run into trouble (endless loop)
            last_time_received = TIMESTAMP_NEVER

        if type_of_data_returned != LatestReceivedType.UNDEFINED:
            self._reset_restart_count_and_collect_stats(position_type)
        else:
            self._handle_proto_timeout(position_type, proto_to_wait_for, type_of_data_returned)

        self.worker_stats()
        return type_of_data_returned, data

    def _handle_proto_timeout(self, position_type, proto_to_wait_for: ProtoIdentifier, type_of_data_returned):
        self.logger.info("Timeout waiting for useful data. Type requested was {}, received {}",
                         proto_to_wait_for, type_of_data_returned)
        self._mitm_mapper.collect_location_stats(self._origin, self.current_location, 0,
                                                 self._waittime_without_delays,
                                                 position_type, 0,
                                                 self._mapping_manager.routemanager_get_mode(
                                                     self._routemanager_name),
                                                 self._transporttype)
        self._restart_count += 1
        restart_thresh = self.get_devicesettings_value("restart_thresh", 5)
        reboot_thresh = self.get_devicesettings_value("reboot_thresh", 3)
        if self._mapping_manager.routemanager_get_route_stats(self._routemanager_name,
                                                              self._origin) is not None:
            if self._init:
                restart_thresh = self.get_devicesettings_value("restart_thresh", 5) * 2
                reboot_thresh = self.get_devicesettings_value("reboot_thresh", 3) * 2
        if self._restart_count > restart_thresh:
            self._reboot_count += 1
            if self._reboot_count > reboot_thresh \
                    and self.get_devicesettings_value("reboot", True):
                self.logger.warning("Too many timeouts - Rebooting device")
                self._reboot(mitm_mapper=self._mitm_mapper)
                raise InternalStopWorkerException

            # self._mitm_mapper.
            self._restart_count = 0
            self.logger.warning("Too many timeouts - Restarting game")
            self._restart_pogo(True, self._mitm_mapper)

    def _reset_restart_count_and_collect_stats(self, position_type):
        self.logger.success('Received data')
        self._reboot_count = 0
        self._restart_count = 0
        self._rec_data_time = datetime.now()
        self._mitm_mapper.collect_location_stats(self._origin, self.current_location, 1,
                                                 self._waittime_without_delays,
                                                 position_type, time.time(),
                                                 self._mapping_manager.routemanager_get_mode(
                                                     self._routemanager_name), self._transporttype)

    def raise_stop_worker_if_applicable(self):
        """
        Checks if the worker is supposed to be stopped or the routemanagers/mappings have changed
        Raises: InternalStopWorkerException
        """
        if not self._mapping_manager.routemanager_present(self._routemanager_name) \
                or self._stop_worker_event.is_set():
            self.logger.error("killed while sleeping")
            raise InternalStopWorkerException
        position_type = self._mapping_manager.routemanager_get_position_type(self._routemanager_name,
                                                                             self._origin)
        if position_type is None:
            self.logger.info("Mappings/Routemanagers have changed, stopping worker to be created again")
            raise InternalStopWorkerException

    def _is_location_within_allowed_range(self, latest_location):
        self.logger.debug2("Checking (data) location reported by {} at {} against real data location {}",
                           self._origin,
                           self.current_location,
                           latest_location)
        distance_to_data = get_distance_of_two_points_in_meters(float(latest_location.lat),
                                                                float(latest_location.lng),
                                                                float(self.current_location.lat),
                                                                float(self.current_location.lng))
        max_distance_of_mode = self._mapping_manager.routemanager_get_max_radius(self._routemanager_name)
        max_distance_for_worker = self._applicationArgs.maximum_valid_distance
        if max_distance_for_worker > max_distance_of_mode > MINIMUM_DISTANCE_ALLOWANCE_FOR_GMO:
            # some modes may be too strict (e.g. quests with 0.0001m calculations for routes)
            # yet, the route may "require" a stricter ruling than max valid distance
            max_distance_for_worker = max_distance_of_mode
        self.logger.debug2("Distance of worker {} to (data) location: {}", self._origin, distance_to_data)
        if distance_to_data > max_distance_for_worker:
            self.logger.debug("Location too far from worker position, max distance allowed: {}m",
                              max_distance_for_worker)
        return distance_to_data <= max_distance_for_worker

    def _start_pogo(self) -> bool:
        pogo_topmost = self._communicator.is_pogo_topmost()
        if pogo_topmost:
            return True
        self._mitm_mapper.set_injection_status(self._origin, False)
        started_pogo: bool = WorkerBase._start_pogo(self)
        if not self._wait_for_injection() or self._stop_worker_event.is_set():
            raise InternalStopWorkerException
        else:
            return started_pogo

    def _wait_for_injection(self):
        self._not_injected_count = 0
        reboot = self.get_devicesettings_value('reboot', True)
        injection_thresh_reboot = 'Unlimited'
        if reboot:
            injection_thresh_reboot = int(self.get_devicesettings_value("injection_thresh_reboot", 20))
        window_check_frequency = 3
        while not self._mitm_mapper.get_injection_status(self._origin):
            self._check_for_mad_job()
            if reboot and self._not_injected_count >= injection_thresh_reboot:
                self.logger.warning("Not injected in time - reboot")
                self._reboot(self._mitm_mapper)
                return False
            self.logger.info("Didn't receive any data yet. (Retry count: {}/{})", self._not_injected_count,
                             injection_thresh_reboot)
            if (self._not_injected_count != 0 and self._not_injected_count % window_check_frequency == 0) \
                    and not self._stop_worker_event.is_set():
                self.logger.info("Retry check_windows while waiting for injection at count {}",
                                 self._not_injected_count)
                self._ensure_pogo_topmost()
            self._not_injected_count += 1
            wait_time = 0
            while wait_time < 20:
                wait_time += 1
                if self._stop_worker_event.is_set():
                    self.logger.error("Killed while waiting for injection")
                    return False
                time.sleep(1)
        return True

    @abstractmethod
    def _check_for_data_content(self, latest, proto_to_wait_for: ProtoIdentifier, timestamp) \
            -> Tuple[LatestReceivedType, Optional[object]]:
        """
        Wait_for_data for each worker
        :return:
        """
        pass

    def _walk_to_location(self, speed: float) -> int:
        """
        Calls the communicator to walk from self.last_location to self.current_location at the speed passed as an arg
        Args:
            speed:

        Returns:

        """
        self._transporttype = 1
        time_before_walk = math.floor(time.time())
        self._communicator.walk_from_to(self.last_location, self.current_location, speed)
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

    def _get_route_manager_settings_and_distance_to_current_location(self):
        if not self._mapping_manager.routemanager_present(self._routemanager_name) \
                or self._stop_worker_event.is_set():
            raise InternalStopWorkerException
        routemanager_settings = self._mapping_manager.routemanager_get_settings(self._routemanager_name)
        distance = get_distance_of_two_points_in_meters(float(self.last_location.lat),
                                                        float(
                                                            self.last_location.lng),
                                                        float(
                                                            self.current_location.lat),
                                                        float(self.current_location.lng))
        self.logger.debug('Moving {} meters to the next position', round(distance, 2))
        return distance, routemanager_settings

    def _clear_quests(self, delayadd, openmenu=True):
        self.logger.debug('{_clear_quests} called')
        if openmenu:
            x, y = self._resocalc.get_coords_quest_menu(self)
            self._communicator.click(int(x), int(y))
            self.logger.debug("_clear_quests Open menu: {}, {}", int(x), int(y))
            time.sleep(6 + int(delayadd))

        x, y = self._resocalc.get_close_main_button_coords(self)
        self._communicator.click(int(x), int(y))
        time.sleep(1.5)
        self.logger.debug('{_clear_quests} finished')

    def _click_pokestop_at_current_location(self, delayadd):
        self.logger.debug('{_open_gym} called')
        time.sleep(.5)
        x, y = self._resocalc.get_gym_click_coords(self)
        self._communicator.click(int(x), int(y))
        time.sleep(.5 + int(delayadd))
        self.logger.debug('{_open_gym} finished')
        return

    def _close_gym(self, delayadd):
        self.logger.debug('{_close_gym} called')
        x, y = self._resocalc.get_close_main_button_coords(self)
        self._communicator.click(int(x), int(y))
        time.sleep(1 + int(delayadd))
        self.logger.debug('{_close_gym} called')

    def _turn_map(self, delayadd):
        self.logger.debug('{_turn_map} called')
        self.logger.info('Turning map')
        x1, x2, y = self._resocalc.get_gym_spin_coords(self)
        self._communicator.swipe(int(x1), int(y), int(x2), int(y))
        time.sleep(int(delayadd))
        self.logger.debug('{_turn_map} called')
        return

    def worker_stats(self):
        self.logger.debug('===============================')
        self.logger.debug('Worker Stats')
        self.logger.debug('Origin: {} [{}]', self._origin, self._dev_id)
        self.logger.debug('Routemanager: {} [{}]', self._routemanager_name, self._area_id)
        self.logger.debug('Restart Counter: {}', self._restart_count)
        self.logger.debug('Reboot Counter: {}', self._reboot_count)
        self.logger.debug('Reboot Option: {}', self.get_devicesettings_value("reboot", True))
        self.logger.debug('Current Pos: {} {}', self.current_location.lat, self.current_location.lng)
        self.logger.debug('Last Pos: {} {}', self.last_location.lat, self.last_location.lng)
        routemanager_status = self._mapping_manager.routemanager_get_route_stats(self._routemanager_name,
                                                                                 self._origin)
        if routemanager_status is None:
            self.logger.warning("Routemanager of {} not available to update stats", self._origin)
            routemanager_status = [None, None]
        else:
            self.logger.debug('Route Pos: {} - Route Length: {}', routemanager_status[0], routemanager_status[1])
        routemanager_init: bool = self._mapping_manager.routemanager_get_init(self._routemanager_name)
        self.logger.debug('Init Mode: {}', routemanager_init)
        self.logger.debug('Last Date/Time of Data: {}', self._rec_data_time)
        self.logger.debug('===============================')
        save_data = {
            'device_id': self._dev_id,
            'currentPos': 'POINT(%s,%s)' % (self.current_location.lat, self.current_location.lng),
            'lastPos': 'POINT(%s,%s)' % (self.last_location.lat, self.last_location.lng),
            'routePos': routemanager_status[0],
            'routeMax': routemanager_status[1],
            'area_id': self._area_id,
            'rebootCounter': self._reboot_count,
            'init': routemanager_init,
            'rebootingOption': self.get_devicesettings_value("reboot", True),
            'restartCounter': self._restart_count,
            'currentSleepTime': self._current_sleep_time
        }
        if self._rec_data_time:
            save_data['lastProtoDateTime'] = 'NOW()'
            self._rec_data_time = None
        self._db_wrapper.save_status(save_data)

    def _worker_specific_setup_stop(self):
        self.logger.info("Stopping pogodroid")
        stop_result = self._communicator.stop_app("com.mad.pogodroid")
        return stop_result

    def _worker_specific_setup_start(self):
        self.logger.info("Starting pogodroid")
        start_result = self._communicator.start_app("com.mad.pogodroid")
        time.sleep(5)
        # won't work if PogoDroid is repackaged!
        self._communicator.passthrough("am startservice com.mad.pogodroid/.services.HookReceiverService")
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
