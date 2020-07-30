import collections
import time
from abc import abstractmethod
from datetime import datetime
from enum import Enum
from typing import Optional

from mapadroid.mitm_receiver.MitmMapper import MitmMapper
from mapadroid.ocr.pogoWindows import PogoWindows
from mapadroid.utils import MappingManager
from mapadroid.utils.geo import get_distance_of_two_points_in_meters
from mapadroid.utils.madGlobals import InternalStopWorkerException
from mapadroid.utils.s2Helper import S2Helper
from mapadroid.websocket.AbstractCommunicator import AbstractCommunicator
from mapadroid.worker.WorkerBase import WorkerBase
from mapadroid.utils.logging import get_logger, LoggerEnums


logger = get_logger(LoggerEnums.worker)
Location = collections.namedtuple('Location', ['lat', 'lng'])


class LatestReceivedType(Enum):
    UNDEFINED = -1
    GYM = 0
    STOP = 2
    MON = 3
    CLEAR = 4
    GMO = 5


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

    def _check_data_distance(self, data):
        max_radius = self._mapping_manager.routemanager_get_max_radius(self._routemanager_name)
        if not max_radius:
            return True
        max_radius: int = self._applicationArgs.maximum_valid_distance \
            if max_radius < self._applicationArgs.maximum_valid_distance else max_radius
        mode = self._mapping_manager.routemanager_get_mode(self._routemanager_name)
        if mode in ["mon_mitm", "iv_mitm"]:
            data_to_check = "wild_pokemon"
        else:
            data_to_check = "forts"
        lat_sum, lng_sum, counter = 0, 0, 0

        if data_to_check == "forts":
            for cell in data:
                if cell[data_to_check]:
                    cell_id = cell["id"]
                    if cell_id < 0:
                        cell_id = cell_id + 2 ** 64
                    lat, lng, _ = S2Helper.get_position_from_cell(cell_id)
                    counter += 1
                    lat_sum += lat
                    lng_sum += lng
        else:
            for cell in data:
                for element in cell[data_to_check]:
                    counter += 1
                    lat_sum += element["latitude"]
                    lng_sum += element["longitude"]

        if counter == 0:
            return None
        avg_lat = lat_sum / counter
        avg_lng = lng_sum / counter
        distance = get_distance_of_two_points_in_meters(float(avg_lat),
                                                        float(avg_lng),
                                                        float(self.current_location.lat),
                                                        float(self.current_location.lng))
        if distance > max_radius:
            self.logger.debug2("Data is too far away!! avg location {}, {} from  data with self.current_location "
                               "location {}, {} - that's a {}m distance with max_radius {} for mode {}", avg_lat,
                               avg_lng, self.current_location.lat, self.current_location.lng, distance, max_radius,
                               mode)
            return False
        else:
            self.logger.debug("Data distance is ok! found avg location {}, {} from data with self.current_location "
                              "location {}, {} - that's a {}m distance with max_radius {} for mode {}", avg_lat,
                              avg_lng, self.current_location.lat, self.current_location.lng, distance, max_radius, mode)
            return True

    def _wait_for_data(self, timestamp: float = None, proto_to_wait_for=106, timeout=None):
        if timestamp is None:
            timestamp = time.time()

        if timeout is None:
            timeout = self.get_devicesettings_value("mitm_wait_timeout", 45)

        # since the GMOs may only contain mons if we are not "too fast" (which is the case when teleporting) after
        # waiting a certain period of time (usually the 2nd GMO), we will multiply the timeout by 2 for mon-modes
        mode = self._mapping_manager.routemanager_get_mode(self._routemanager_name)
        if mode in ["mon_mitm", "iv_mitm"] or self._mapping_manager.routemanager_get_init(
                self._routemanager_name):
            timeout *= 2
        # let's fetch the latest data to add the offset to timeout (in case device and server times are off...)
        latest = self._mitm_mapper.request_latest(self._origin)
        timestamp_last_data = latest.get("timestamp_last_data", 0)
        timestamp_last_received = latest.get("timestamp_receiver", 0)

        # we can now construct the rough estimate of the diff of time of mobile vs time of server, subtract our
        # timestamp by the diff
        # TODO: discuss, probably wiser to add to timeout or get the diff of how long it takes for RGC to issue a cmd
        timestamp = timestamp - (timestamp_last_received - timestamp_last_data)

        self.logger.info('Waiting for data after {}', datetime.fromtimestamp(timestamp))
        data_requested = LatestReceivedType.UNDEFINED

        failover_timestamp: int = time.time()

        while data_requested == LatestReceivedType.UNDEFINED and \
                (timestamp + timeout >= int(time.time()) and int(failover_timestamp + timeout) >= int(time.time())) \
                and not self._stop_worker_event.is_set():
            latest = self._mitm_mapper.request_latest(self._origin)
            latest_location: Optional[Location] = latest.get("location", None)
            check_data = True
            if (proto_to_wait_for == 106 and latest_location is not None and
                    latest_location.lat != 0.0 and latest_location.lng != 0.0):
                self.logger.debug("Checking worker location {} against real data location {}", self.current_location,
                                  latest_location)
                distance_to_data = get_distance_of_two_points_in_meters(float(latest_location.lat),
                                                                        float(latest_location.lng),
                                                                        float(self.current_location.lat),
                                                                        float(self.current_location.lng))
                max_distance_of_mode = self._mapping_manager.routemanager_get_max_radius(self._routemanager_name)
                max_distance_for_worker: int = self._applicationArgs.maximum_valid_distance \
                    if max_distance_of_mode < self._applicationArgs.maximum_valid_distance else max_distance_of_mode
                self.logger.debug("Distance of worker {} to data location: {}", self._origin, distance_to_data)
                if max_distance_for_worker and distance_to_data > max_distance_for_worker:
                    self.logger.debug("Real data too far from worker position, waiting...")
                    check_data = False

            if check_data:
                data_requested = self._wait_data_worker(
                    latest, proto_to_wait_for, timestamp)
            if not self._mapping_manager.routemanager_present(self._routemanager_name) \
                    or self._stop_worker_event.is_set():
                self.logger.error("killed while sleeping")
                raise InternalStopWorkerException

            time.sleep(1)

        position_type = self._mapping_manager.routemanager_get_position_type(self._routemanager_name,
                                                                             self._origin)
        if position_type is None:
            self.logger.warning("Mappings/Routemanagers have changed, stopping worker to be created again")
            raise InternalStopWorkerException
        if data_requested != LatestReceivedType.UNDEFINED:
            self.logger.success('Got the data requested')
            self._reboot_count = 0
            self._restart_count = 0
            self._rec_data_time = datetime.now()

            self._mitm_mapper.collect_location_stats(self._origin, self.current_location, 1,
                                                     self._waittime_without_delays,
                                                     position_type, time.time(),
                                                     self._mapping_manager.routemanager_get_mode(
                                                         self._routemanager_name), self._transporttype)

        else:
            # TODO: timeout also happens if there is no useful data such as mons nearby in mon_mitm mode, we need to
            # TODO: be more precise (timeout vs empty data)
            self.logger.warning("Timeout waiting for data")

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
                        and self.get_devicesettings_value("reboot", False):
                    self.logger.error("Too many timeouts - Rebooting device")
                    self._reboot(mitm_mapper=self._mitm_mapper)
                    raise InternalStopWorkerException

                # self._mitm_mapper.
                self._restart_count = 0
                self.logger.error("Too many timeouts - Restarting game")
                self._restart_pogo(True, self._mitm_mapper)

        self.worker_stats()
        return data_requested

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
        reboot = self.get_devicesettings_value('reboot', False)
        injection_thresh_reboot = 'Unlimited'
        if reboot:
            injection_thresh_reboot = int(self.get_devicesettings_value("injection_thresh_reboot", 20))
        window_check_frequency = 3
        while not self._mitm_mapper.get_injection_status(self._origin):
            self._check_for_mad_job()
            if reboot and self._not_injected_count >= injection_thresh_reboot:
                self.logger.error("Not injected in time - reboot")
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
    def _wait_data_worker(self, latest, proto_to_wait_for, timestamp):
        """
        Wait_for_data for each worker
        :return:
        """
        pass

    def _clear_quests(self, delayadd, openmenu=True):
        self.logger.debug('{_clear_quests} called')
        if openmenu:
            x, y = self._resocalc.get_coords_quest_menu(self)
            self._communicator.click(int(x), int(y))
            self.logger.debug("_clear_quests Open menu: {}, {}", int(x), int(y))
            time.sleep(6 + int(delayadd))

        if self._enhanced_mode:
            x, y = self._resocalc.get_close_main_button_coords(self)
            self._communicator.click(int(x), int(y))
            return

        x, y = self._resocalc.get_quest_listview(self)
        self._communicator.click(int(x), int(y))
        self.logger.debug("_clear_quests Open field: {}, {}", int(x), int(y))
        time.sleep(4 + int(delayadd))

        trashcancheck = self._get_trash_positions(full_screen=True)
        self.logger.debug("_clear_quests Found trash: {}", trashcancheck)
        if trashcancheck is None:
            self.logger.error('Could not find any trashcan - abort')
            return
        if len(trashcancheck) == 0:
            self._clear_quests_failcount += 1
            if self._clear_quests_failcount < 3:
                self.logger.warning("Could not find any trashcan on a valid screenshot {} time(s) in a row!",
                                    self._clear_quests_failcount)
            else:
                self._clear_quests_failcount = 0
                self.logger.error("Unable to clear quests 3 times in a row. Restart pogo ...")
                if not self._restart_pogo(mitm_mapper=self._mitm_mapper):
                    # TODO: put in loop, count up for a reboot ;)
                    raise InternalStopWorkerException
                return
        else:
            self.logger.info("Found {} trashcan(s) on screen", len(trashcancheck))
        # get confirm box coords
        x, y = self._resocalc.get_confirm_delete_quest_coords(self)

        for trash in range(len(trashcancheck)):
            self._clear_quests_failcount = 0
            self.set_devicesettings_value('last_questclear_time', time.time())
            self.logger.info("Delete old quest {}", int(trash) + 1)
            for i in range(3):
                self.logger.debug("repeated trash click #{}", i + 1)
                self._communicator.click(int(trashcancheck[0].x), int(trashcancheck[0].y))
                time.sleep(0.3 + int(delayadd))
            self.logger.debug("final trash click ...")
            self._communicator.click(int(trashcancheck[0].x), int(trashcancheck[0].y))
            time.sleep(2.5 + int(delayadd))
            self._communicator.click(int(x), int(y))
            time.sleep(1 + int(delayadd))

        x, y = self._resocalc.get_close_main_button_coords(self)
        self._communicator.click(int(x), int(y))

        time.sleep(1.5)

        self.logger.debug('{_clear_quests} finished')
        return

    def _open_gym(self, delayadd):
        self.logger.debug('{_open_gym} called')
        time.sleep(.5)
        x, y = self._resocalc.get_gym_click_coords(self)
        self._communicator.click(int(x), int(y))
        time.sleep(.5 + int(delayadd))
        self.logger.debug('{_open_gym} finished')
        return

    def _spin_wheel(self, delayadd):
        self.logger.debug('{_spin_wheel} called')
        x1, x2, y = self._resocalc.get_gym_spin_coords(self)
        self._communicator.swipe(int(x1), int(y), int(x2), int(y))
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
        self.logger.debug('Reboot Option: {}', self.get_devicesettings_value("reboot", False))
        self.logger.debug('Current Pos: {} {}', self.current_location.lat, self.current_location.lng)
        self.logger.debug('Last Pos: {} {}', self.last_location.lat, self.last_location.lng)
        routemanager_status = self._mapping_manager.routemanager_get_route_stats(self._routemanager_name,
                                                                                 self._origin)
        if routemanager_status is None:
            self.logger.warning("Routemanager not available")
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
            'rebootingOption': self.get_devicesettings_value("reboot", False),
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
