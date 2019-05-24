import collections
import math
import time
from abc import abstractmethod
from datetime import datetime
from enum import Enum

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


class MITMBase(WorkerBase):
    def __init__(self, args, id, last_known_state, websocket_handler,
                 walker_routemanager, devicesettings, db_wrapper, mitm_mapper, pogoWindowManager,
                 NoOcr=False, walker=None):
        WorkerBase.__init__(self, args, id, last_known_state, websocket_handler,
                            walker_routemanager, devicesettings, db_wrapper=db_wrapper, NoOcr=True,
                            pogoWindowManager=pogoWindowManager, walker=walker)

        self._reboot_count = 0
        self._restart_count = 0
        self._rec_data_time = ""
        self._mitm_mapper = mitm_mapper
        self._latest_encounter_update = 0
        self._encounter_ids = {}

        self._mitm_mapper.collect_location_stats(self._id, self.current_location, 1, time.time(), 2, 0,
                                                 self._walker_routemanager.get_walker_type(), 99)

    def _wait_for_data(self, timestamp: float = time.time(), proto_to_wait_for=106, timeout=None):
        if timeout is None:
            timeout = self._devicesettings.get("mitm_wait_timeout", 45)

        # let's fetch the latest data to add the offset to timeout (in case phone and server times are off...)
        latest = self._mitm_mapper.request_latest(self._id)
        timestamp_last_data = latest.get("timestamp_last_data", None)
        timestamp_last_received = latest.get("timestamp_receiver", None)

        # we can now construct the rough estimate of the diff of time of mobile vs time of server, subtract our
        # timestamp by the diff
        # TODO: discuss, probably wiser to add to timeout or get the diff of how long it takes for RGC to issue a cmd
        timestamp = timestamp - (timestamp_last_received - timestamp_last_data)

        # if timestamp_last_data is not None and timestamp_last_received is not None:
        #     # add the difference of the two timestamps to timeout
        #     timeout += (timestamp_last_received - timestamp_last_data)

        logger.info('Waiting for data after {}',
                    datetime.fromtimestamp(timestamp))
        data_requested = LatestReceivedType.UNDEFINED

        while (data_requested == LatestReceivedType.UNDEFINED
                and timestamp + timeout >= math.floor(time.time())):
            latest = self._mitm_mapper.request_latest(self._id)
            data_requested = self._wait_data_worker(
                latest, proto_to_wait_for, timestamp)
            time.sleep(1)

        if data_requested != LatestReceivedType.UNDEFINED:
            logger.debug('Got the data requested...')
            self._reboot_count = 0
            self._restart_count = 0
            self._rec_data_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            self._mitm_mapper.collect_location_stats(self._id, self.current_location, 1, self._waittime_without_delays,
                                                     self._walker_routemanager.get_position_type(self._id), time.time(),
                                                     self._walker_routemanager.get_walker_type(), self._transporttype)
        else:
            # TODO: timeout also happens if there is no useful data such as mons nearby in mon_mitm mode, we need to
            # TODO: be more precise (timeout vs empty data)
            logger.warning("Timeout waiting for data")

            self._mitm_mapper.collect_location_stats(self._id, self.current_location, 0, self._waittime_without_delays,
                                                     self._walker_routemanager.get_position_type(self._id), 0,
                                                     self._walker_routemanager.get_walker_type(), self._transporttype)

            self._restart_count += 1

            restart_thresh = self._devicesettings.get("restart_thresh", 5)
            reboot_thresh = self._devicesettings.get("reboot_thresh", 3)
            if self._walker_routemanager is not None:
                if self._init:
                    restart_thresh = self._devicesettings.get(
                        "restart_thresh", 5) * 2
                    reboot_thresh = self._devicesettings.get(
                        "reboot_thresh", 3) * 2

            if self._restart_count > restart_thresh:
                self._reboot_count += 1
                if self._reboot_count > reboot_thresh \
                        and self._devicesettings.get("reboot", False):
                    logger.error("Rebooting {}", str(self._id))
                    self._reboot(mitm_mapper=self._mitm_mapper)
                    raise InternalStopWorkerException

                # self._mitm_mapper.
                self._restart_count = 0
                self._restart_pogo(True, self._mitm_mapper)

        self.worker_stats()
        return data_requested

    def _wait_for_injection(self):
        self._not_injected_count = 0
        while not self._mitm_mapper.get_injection_status(self._id):
            if self._not_injected_count >= 20:
                logger.error("Worker {} not get injected in time - reboot", str(self._id))
                self._reboot(self._mitm_mapper)
                return False
            logger.info("Worker {} is not injected till now (Count: {})", str(self._id), str(self._not_injected_count))
            if self._stop_worker_event.isSet():
                logger.error("Worker {} get killed while waiting for injection", str(self._id))
                return False
            self._not_injected_count += 1
            time.sleep(20)
        return True

    @abstractmethod
    def _wait_data_worker(self, latest, proto_to_wait_for, timestamp):
        """
        Wait_for_data for each worker
        :return:
        """
        pass

    def _clear_quests(self, delayadd):
        logger.debug('{_clear_quests} called')
        x, y = self._resocalc.get_coords_quest_menu(self)[0], \
            self._resocalc.get_coords_quest_menu(self)[1]
        self._communicator.click(int(x), int(y))
        time.sleep(2 + int(delayadd))

        trashcancheck = self._get_trash_positions()
        if trashcancheck is None:
            logger.error('Could not find any trashcan - abort')
            return
        logger.info("Found {} trashcan(s) on screen", len(trashcancheck))
        # get confirm box coords
        x, y = self._resocalc.get_confirm_delete_quest_coords(self)[0], \
               self._resocalc.get_confirm_delete_quest_coords(self)[1]

        for trash in range(len(trashcancheck)):
            logger.info("Delete old quest {}", int(trash)+1)
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
        routemanager = self._walker_routemanager
        logger.debug('===============================')
        logger.debug('Worker Stats')
        logger.debug('Origin: {}', str(self._id))
        logger.debug('Routemanager: {}', str(routemanager.name))
        logger.debug('Restart Counter: {}', str(self._restart_count))
        logger.debug('Reboot Counter: {}', str(self._reboot_count))
        logger.debug('Reboot Option: {}', str(
            self._devicesettings.get("reboot", False)))
        logger.debug('Current Pos: {} {}', str(
            self.current_location.lat), str(self.current_location.lng))
        logger.debug('Last Pos: {} {}', str(
            self.last_location.lat), str(self.last_location.lng))
        logger.debug('Route Pos: {} - Route Length: {}', str(
            routemanager.get_route_status()[0]), str(routemanager.get_route_status()[1]))
        logger.debug('Init Mode: {}', str(routemanager.init))
        logger.debug('Last Date/Time of Data: {}', str(self._rec_data_time))
        logger.debug('===============================')

        dataToSave = {
            'Origin':            self._id,
            'Routemanager':      str(routemanager.name),
            'RebootCounter':     str(self._reboot_count),
            'RestartCounter':    str(self._restart_count),
            'RebootingOption':   str(self._devicesettings.get("reboot", False)),
            'CurrentPos':        str(self.current_location.lat) + ", " + str(self.current_location.lng),
            'LastPos':           str(self.last_location.lat) + ", " + str(self.last_location.lng),
            'RoutePos':          str(routemanager.get_route_status()[0]),
            'RouteMax':          str(routemanager.get_route_status()[1]),
            'Init':              str(routemanager.init),
            'LastProtoDateTime': str(self._rec_data_time)
        }

        self._db_wrapper.save_status(dataToSave)
