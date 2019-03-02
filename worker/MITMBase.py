import datetime
import logging
import math
import time
from abc import abstractmethod

from utils.madGlobals import InternalStopWorkerException
from worker.WorkerBase import WorkerBase

log = logging.getLogger(__name__)


class MITMBase(WorkerBase):
    def __init__(self, args, id, last_known_state, websocket_handler, route_manager_daytime,
                 route_manager_nighttime, devicesettings, db_wrapper, timer, mitm_mapper, pogoWindowManager,
                 NoOcr=False):
        WorkerBase.__init__(self, args, id, last_known_state, websocket_handler, route_manager_daytime,
                            route_manager_nighttime, devicesettings, db_wrapper=db_wrapper, NoOcr=True, timer=timer,
                            pogoWindowManager=pogoWindowManager)

        self._reboot_count = 0
        self._restart_count = 0
        self._rec_data_time = ""
        self._mitm_mapper = mitm_mapper

        #if not NoOcr:
        #    from ocr.pogoWindows import PogoWindows
        #    self._pogoWindowManager = PogoWindows(self._communicator, args.temp_path)

    def _wait_for_data(self, timestamp, proto_to_wait_for=106, timeout=False):
        if not timeout:
            timeout = self._devicesettings.get("mitm_wait_timeout", 45)

        log.info('Waiting for data after %s' % str(timestamp))
        data_requested = None

        while data_requested is None and timestamp + timeout >= math.floor(time.time()):
            latest = self._mitm_mapper.request_latest(self._id)
            data_requested = self._wait_data_worker(latest, proto_to_wait_for, timestamp)
            time.sleep(1)

        if data_requested is not None:
            log.info('Got the data requested...')
            self._reboot_count = 0
            self._restart_count = 0
            self._rec_data_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            # TODO: timeout also happens if there is no useful data such as mons nearby in mon_mitm mode, we need to
            # TODO: be more precise (timeout vs empty data)
            log.warning("Timeout waiting for data")
            try:
                current_routemanager = self._get_currently_valid_routemanager()
            except InternalStopWorkerException as e:
                log.info("Worker %s is to be stopped due to invalid routemanager/mode switch" % str(self._id))
                raise InternalStopWorkerException
            self._restart_count += 1

            restart_thresh = self._devicesettings.get("restart_thresh", 5)
            reboot_thresh = self._devicesettings.get("reboot_thresh", 3)
            if current_routemanager.init:
                restart_thresh = self._devicesettings.get("restart_thresh", 5) * 2
                reboot_thresh = self._devicesettings.get("reboot_thresh", 3) * 2

            if self._restart_count > restart_thresh:
                self._reboot_count += 1
                if self._reboot_count > reboot_thresh \
                        and self._devicesettings.get("reboot", False):
                    log.error("Rebooting %s" % str(self._id))
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
        log.debug('{_clear_quests} called')
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

        log.debug('{_clear_quests} finished')
        return

    def _open_gym(self, delayadd):
        log.debug('{_open_gym} called')
        time.sleep(.5)
        x, y = self._resocalc.get_gym_click_coords(self)[0], self._resocalc.get_gym_click_coords(self)[1]
        self._communicator.click(int(x), int(y))
        time.sleep(.5 + int(delayadd))
        log.debug('{_open_gym} finished')
        return

    def _spin_wheel(self, delayadd):
        log.debug('{_spin_wheel} called')
        x1, x2, y = self._resocalc.get_gym_spin_coords(self)[0], self._resocalc.get_gym_spin_coords(self)[1], \
                    self._resocalc.get_gym_spin_coords(self)[2]
        self._communicator.swipe(int(x1), int(y), int(x2), int(y))
        return

    def _close_gym(self, delayadd):
        log.debug('{_close_gym} called')
        x, y = self._resocalc.get_close_main_button_coords(self)[0], \
               self._resocalc.get_close_main_button_coords(self)[1]
        self._communicator.click(int(x), int(y))
        time.sleep(1 + int(delayadd))
        log.debug('{_close_gym} called')

    def _turn_map(self, delayadd):
        log.debug('{_turn_map} called')
        x1, x2, y = self._resocalc.get_gym_spin_coords(self)[0], self._resocalc.get_gym_spin_coords(self)[1], \
                    self._resocalc.get_gym_spin_coords(self)[2]
        self._communicator.swipe(int(x1), int(y), int(x2), int(y))
        time.sleep(int(delayadd))
        log.debug('{_turn_map} called')
        return

    def worker_stats(self):
        routemanager = self._get_currently_valid_routemanager()
        log.debug('===============================')
        log.debug('Worker Stats')
        log.debug('Origin: %s' % str(self._id))
        log.debug('Routemanager: %s' % str(routemanager.name))
        log.debug('Restart Counter: %s' % str(self._restart_count))
        log.debug('Reboot Counter: %s' % str(self._reboot_count))
        log.debug('Reboot Option: %s' % str(self._devicesettings.get("reboot", False)))
        log.debug('Current Pos: %s %s' % (str(self.current_location.lat),
                                          str(self.current_location.lng)))
        log.debug('Last Pos: %s %s' % (str(self.last_location.lat),
                                       str(self.last_location.lng)))
        log.debug('Route Pos: %s - Route Length: %s ' % (str(routemanager.get_route_status()[0]),
                                                         str(routemanager.get_route_status()[1])))
        log.debug('Init Mode: %s' % str(routemanager.init))
        log.debug('Last Date/Time of Data: %s' % str(self._rec_data_time))
        log.debug('===============================')

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

