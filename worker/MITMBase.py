import collections
import time
import math
from abc import abstractmethod
from datetime import datetime
from enum import Enum

from mitm_receiver.MitmMapper import MitmMapper
from ocr.pogoWindows import PogoWindows
from utils.MappingManager import MappingManager
from utils.logging import logger
from utils.madGlobals import InternalStopWorkerException
from worker.WorkerBase import WorkerBase

Location = collections.namedtuple('Location', ['lat', 'lng'])


class LatestReceivedType(Enum):
    UNDEFINED = -1
    GYM = 0
    STOP = 2
    MON = 3
    CLEAR = 4
    GMO = 5


class MITMBase(WorkerBase):
    def __init__(self, args, id, last_known_state, websocket_handler, mapping_manager: MappingManager,
                 routemanager_name: str, db_wrapper, mitm_mapper: MitmMapper, pogoWindowManager: PogoWindows,
                 NoOcr=False, walker=None):
        WorkerBase.__init__(self, args, id, last_known_state, websocket_handler,
                            mapping_manager=mapping_manager, routemanager_name=routemanager_name,
                            db_wrapper=db_wrapper, NoOcr=True,
                            pogoWindowManager=pogoWindowManager, walker=walker)

        self._reboot_count = 0
        self._restart_count = 0
        self._screendetection_count = 0
        self._rec_data_time = ""
        self._mitm_mapper = mitm_mapper
        self._latest_encounter_update = 0
        self._encounter_ids = {}
        self._current_sleep_time = 0

        self._mitm_mapper.collect_location_stats(self._id, self.current_location, 1, time.time(), 2, 0,
                                                 self._mapping_manager.routemanager_get_mode(self._routemanager_name),
                                                 99)

    def _wait_for_data(self, timestamp: float = None, proto_to_wait_for=106, timeout=None):
        if timestamp is None:
            timestamp = time.time()

        if timeout is None:
            timeout = self.get_devicesettings_value("mitm_wait_timeout", 45)

        # since the GMOs may only contain mons if we are not "too fast" (which is the case when teleporting) after
        # waiting a certain period of time (usually the 2nd GMO), we will multiply the timeout by 2 for mon-modes
        mode = self._mapping_manager.routemanager_get_mode(self._routemanager_name)
        if mode in ["mon_mitm", "iv_mitm"] or self._mapping_manager.routemanager_get_init(self._routemanager_name):
            timeout *= 2
        # let's fetch the latest data to add the offset to timeout (in case device and server times are off...)
        latest = self._mitm_mapper.request_latest(self._id)
        timestamp_last_data = latest.get("timestamp_last_data", 0)
        timestamp_last_received = latest.get("timestamp_receiver", 0)

        # we can now construct the rough estimate of the diff of time of mobile vs time of server, subtract our
        # timestamp by the diff
        # TODO: discuss, probably wiser to add to timeout or get the diff of how long it takes for RGC to issue a cmd
        timestamp = timestamp - (timestamp_last_received - timestamp_last_data)

        logger.info('Waiting for data after {}',
                    datetime.fromtimestamp(timestamp))
        data_requested = LatestReceivedType.UNDEFINED

        while data_requested == LatestReceivedType.UNDEFINED and timestamp + timeout >= int(time.time()) \
                and not self._stop_worker_event.is_set():
            latest = self._mitm_mapper.request_latest(self._id)
            data_requested = self._wait_data_worker(
                latest, proto_to_wait_for, timestamp)
            if not self._mapping_manager.routemanager_present(self._routemanager_name) \
                    or self._stop_worker_event.is_set():
                logger.error("Worker {} get killed while sleeping", str(self._id))
                raise InternalStopWorkerException

            time.sleep(1)

        position_type = self._mapping_manager.routemanager_get_position_type(self._routemanager_name, self._id)
        if position_type is None:
            logger.warning("Mappings/Routemanagers have changed, stopping worker to be created again")
            raise InternalStopWorkerException
        if data_requested != LatestReceivedType.UNDEFINED:
            logger.debug('Got the data requested...')
            self._reboot_count = 0
            self._restart_count = 0
            self._rec_data_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            self._mitm_mapper.collect_location_stats(self._id, self.current_location, 1, self._waittime_without_delays,
                                                     position_type, time.time(),
                                                     self._mapping_manager.routemanager_get_mode(
                                                         self._routemanager_name), self._transporttype)
        else:
            # TODO: timeout also happens if there is no useful data such as mons nearby in mon_mitm mode, we need to
            # TODO: be more precise (timeout vs empty data)
            logger.warning("Timeout waiting for data")

            self._mitm_mapper.collect_location_stats(self._id, self.current_location, 0, self._waittime_without_delays,
                                                     position_type, 0,
                                                     self._mapping_manager.routemanager_get_mode(self._routemanager_name),
                                                     self._transporttype)

            self._restart_count += 1

            restart_thresh = self.get_devicesettings_value("restart_thresh", 5)
            reboot_thresh = self.get_devicesettings_value("reboot_thresh", 3)
            if self._mapping_manager.routemanager_get_route_stats(self._routemanager_name, self._id) is not None:
                if self._init:
                    restart_thresh = self.get_devicesettings_value("restart_thresh", 5) * 2
                    reboot_thresh = self.get_devicesettings_value("reboot_thresh", 3) * 2

            if self._restart_count > restart_thresh:
                self._reboot_count += 1
                if self._reboot_count > reboot_thresh \
                        and self.get_devicesettings_value("reboot", False):
                    logger.error("Too many timeouts - Rebooting device {}", str(self._id))
                    self._reboot(mitm_mapper=self._mitm_mapper)
                    raise InternalStopWorkerException

                # self._mitm_mapper.
                self._restart_count = 0
                logger.error("Too many timeouts - Restarting game on {}", str(self._id))
                self._restart_pogo(True, self._mitm_mapper)

        self.worker_stats()
        return data_requested

    def _wait_for_injection(self):
        self._not_injected_count = 0
        injection_thresh_reboot = int(self.get_devicesettings_value("injection_thresh_reboot", 20))
        while not self._mitm_mapper.get_injection_status(self._id):

            self._check_for_mad_job()

            if self._not_injected_count >= injection_thresh_reboot:
                logger.error("Worker {} not injected in time - reboot", str(self._id))
                self._reboot(self._mitm_mapper)
                return False
            logger.info("PogoDroid on worker {} didn't connect yet. Probably not injected? (Count: {}/{})",
                        str(self._id), str(self._not_injected_count), str(injection_thresh_reboot))
            if self._not_injected_count in [3, 6, 9, 15, 18] and not self._stop_worker_event.is_set():
                logger.info("Worker {} will retry check_windows while waiting for injection at count {}",
                            str(self._id), str(self._not_injected_count))
                self._check_windows()
            self._not_injected_count += 1
            wait_time = 0
            while wait_time < 20:
                wait_time += 1
                if self._stop_worker_event.is_set():
                    logger.error("Worker {} killed while waiting for injection", str(self._id))
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
        logger.debug('{_clear_quests} called')
        if openmenu:
            x, y = self._resocalc.get_coords_quest_menu(self)[0], \
                self._resocalc.get_coords_quest_menu(self)[1]
            self._communicator.click(int(x), int(y))
            time.sleep(6 + int(delayadd))

        trashcancheck = self._get_trash_positions()
        if trashcancheck is None:
            logger.error('Could not find any trashcan - abort')
            return
        logger.info("Found {} trashcan(s) on screen", len(trashcancheck))
        # get confirm box coords
        x, y = self._resocalc.get_confirm_delete_quest_coords(self)[0], \
            self._resocalc.get_confirm_delete_quest_coords(self)[1]

        for trash in range(len(trashcancheck)):
            logger.info("Delete old quest {}", int(trash) + 1)
            self._communicator.click(int(trashcancheck[0].x), int(trashcancheck[0].y))
            time.sleep(1 + int(delayadd))
            self._communicator.click(int(x), int(y))
            time.sleep(1 + int(delayadd))

        x, y = self._resocalc.get_close_main_button_coords(self)[0], \
            self._resocalc.get_close_main_button_coords(self)[1]
        self._communicator.click(int(x), int(y))

        time.sleep(1.5)

        logger.debug('{_clear_quests} finished')
        return

    def _open_gym(self, delayadd):
        logger.debug('{_open_gym} called')
        time.sleep(.5)
        x, y = self._resocalc.get_gym_click_coords(
            self)[0], self._resocalc.get_gym_click_coords(self)[1]
        self._communicator.click(int(x), int(y))
        time.sleep(.5 + int(delayadd))
        logger.debug('{_open_gym} finished')
        return

    def _spin_wheel(self, delayadd):
        logger.debug('{_spin_wheel} called')
        x1, x2, y = self._resocalc.get_gym_spin_coords(self)[0], self._resocalc.get_gym_spin_coords(self)[1], \
            self._resocalc.get_gym_spin_coords(self)[2]
        self._communicator.swipe(int(x1), int(y), int(x2), int(y))
        return

    def _close_gym(self, delayadd):
        logger.debug('{_close_gym} called')
        x, y = self._resocalc.get_close_main_button_coords(self)[0], \
            self._resocalc.get_close_main_button_coords(self)[1]
        self._communicator.click(int(x), int(y))
        time.sleep(1 + int(delayadd))
        logger.debug('{_close_gym} called')

    def _turn_map(self, delayadd):
        logger.debug('{_turn_map} called')
        logger.info('Turning map')
        x1, x2, y = self._resocalc.get_gym_spin_coords(self)[0], self._resocalc.get_gym_spin_coords(self)[1], \
            self._resocalc.get_gym_spin_coords(self)[2]
        self._communicator.swipe(int(x1), int(y), int(x2), int(y))
        time.sleep(int(delayadd))
        logger.debug('{_turn_map} called')
        return

    def worker_stats(self):
        logger.debug('===============================')
        logger.debug('Worker Stats')
        logger.debug('Origin: {}', str(self._id))
        logger.debug('Routemanager: {}', str(self._routemanager_name))
        logger.debug('Restart Counter: {}', str(self._restart_count))
        logger.debug('Reboot Counter: {}', str(self._reboot_count))
        logger.debug('Reboot Option: {}', str(
            self.get_devicesettings_value("reboot", False)))
        logger.debug('Current Pos: {} {}', str(
            self.current_location.lat), str(self.current_location.lng))
        logger.debug('Last Pos: {} {}', str(
            self.last_location.lat), str(self.last_location.lng))
        routemanager_status = self._mapping_manager.routemanager_get_route_stats(self._routemanager_name, self._id)
        if routemanager_status is None:
            logger.warning("Routemanager not available")
            routemanager_status = [None, None]
        else:
            logger.debug('Route Pos: {} - Route Length: {}', str(routemanager_status[0]), str(routemanager_status[1]))
        routemanager_init: bool = self._mapping_manager.routemanager_get_init(self._routemanager_name)
        logger.debug('Init Mode: {}', str(routemanager_init))
        logger.debug('Last Date/Time of Data: {}', str(self._rec_data_time))
        logger.debug('===============================')

        dataToSave = {
            'Origin':            self._id,
            'Routemanager':      str(self._routemanager_name),
            'RebootCounter':     str(self._reboot_count),
            'RestartCounter':    str(self._restart_count),
            'RebootingOption':   str(self.get_devicesettings_value("reboot", False)),
            'CurrentPos':        str(self.current_location.lat) + ", " + str(self.current_location.lng),
            'LastPos':           str(self.last_location.lat) + ", " + str(self.last_location.lng),
            'RoutePos':          str(routemanager_status[0]),
            'RouteMax':          str(routemanager_status[1]),
            'Init':              str(routemanager_init),
            'LastProtoDateTime': str(self._rec_data_time),
            'CurrentSleepTime': str(self._current_sleep_time)
        }

        self._db_wrapper.save_status(dataToSave)
