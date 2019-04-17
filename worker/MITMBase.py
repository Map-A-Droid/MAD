import collections
import math
import time
from abc import abstractmethod
from datetime import datetime

from utils.logging import logger
from utils.madGlobals import InternalStopWorkerException
from worker.WorkerBase import WorkerBase

Location = collections.namedtuple('Location', ['lat', 'lng'])


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

        if self._devicesettings.get('last_mode', None) is not None and \
                self._devicesettings['last_mode'] in ("raids_mitm", "mon_mitm", "iv_mitm", "raids_ocr"):
            logger.info('Last Mode not pokestop - reset saved location')
            self.last_location = Location(0.0, 0.0)
        self._devicesettings['last_mode'] = self._walker_routemanager.mode

    def _wait_for_data(self, timestamp, proto_to_wait_for=106, timeout=False):
        if not timeout:
            timeout = self._devicesettings.get("mitm_wait_timeout", 45)

        logger.info('Waiting for data after {}',
                    datetime.fromtimestamp(timestamp))
        data_requested = None

        while data_requested is None and timestamp + timeout >= math.floor(time.time()):
            latest = self._mitm_mapper.request_latest(self._id)
            data_requested = self._wait_data_worker(
                latest, proto_to_wait_for, timestamp)
            time.sleep(1)

        if data_requested is not None:
            logger.info('Got the data requested...')
            self._reboot_count = 0
            self._restart_count = 0
            self._rec_data_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            # TODO: timeout also happens if there is no useful data such as mons nearby in mon_mitm mode, we need to
            # TODO: be more precise (timeout vs empty data)
            logger.warning("Timeout waiting for data")

            current_routemanager = self._walker_routemanager
            self._restart_count += 1

            restart_thresh = self._devicesettings.get("restart_thresh", 5)
            reboot_thresh = self._devicesettings.get("reboot_thresh", 3)
            if current_routemanager is not None:
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
                    self._reboot()
                    raise InternalStopWorkerException

                self._restart_count = 0
                self._restart_pogo(True)

        self.worker_stats()
        return data_requested

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
        time.sleep(1 + int(delayadd))

        x, y = self._resocalc.get_delete_quest_coords(self)[0], \
            self._resocalc.get_delete_quest_coords(self)[1]
        self._communicator.click(int(x), int(y))
        time.sleep(1 + int(delayadd))

        x, y = self._resocalc.get_confirm_delete_quest_coords(self)[0], \
            self._resocalc.get_confirm_delete_quest_coords(self)[1]
        self._communicator.click(int(x), int(y))
        time.sleep(1 + int(delayadd))

        x, y = self._resocalc.get_close_main_button_coords(self)[0], \
            self._resocalc.get_close_main_button_coords(self)[1]
        self._communicator.click(int(x), int(y))

        time.sleep(2)

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
