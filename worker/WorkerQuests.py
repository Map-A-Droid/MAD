import logging
import math
import time
from threading import Event, Thread

from utils.geo import get_distance_of_two_points_in_meters
from utils.madGlobals import (InternalStopWorkerException,
                              WebsocketWorkerRemovedException)
from worker.WorkerBase import WorkerBase

log = logging.getLogger(__name__)


class WorkerQuests(WorkerBase):
    def _valid_modes(self):
        return ["pokestops"]

    def __init__(self, args, id, last_known_state, websocket_handler, route_manager_daytime, route_manager_nighttime,
                 mitm_mapper, devicesettings, db_wrapper, timer):
        WorkerBase.__init__(self, args, id, last_known_state, websocket_handler, route_manager_daytime,
                            route_manager_nighttime, devicesettings, db_wrapper=db_wrapper, NoOcr=False, timer=timer)
        self.first_round = True
        self.clear_thread = None
        # 0 => None
        # 1 => clear box
        # 2 => clear quest
        self.clear_thread_task = 0
        self._mitm_mapper = mitm_mapper
        self.__data_error_counter = 0
        self._start_inventory_clear = Event()
        self._delay_add = int(self._devicesettings.get("vps_delay", 0))
        self.__reboot_count = 0
        self.__restart_count = 0

    def _pre_work_loop(self):
        if self.clear_thread is not None:
            return
        self.clear_thread = Thread(name="clear_thread_%s" % str(
            self._id), target=self._clear_thread)
        self.clear_thread.daemon = True
        self.clear_thread.start()
        self._get_screen_size()

        reached_main_menu = self._check_pogo_main_screen(5, True)
        if not reached_main_menu:
            if not self._restart_pogo():
                # TODO: put in loop, count up for a reboot ;)
                raise InternalStopWorkerException

    def _health_check(self):
        """
        Not gonna check for main screen here since we will do health checks in post_move_location_routine
        :return:
        """
        pass

    def _pre_location_update(self):
        self._start_inventory_clear.set()
        self._update_injection_settings()

    def _move_to_location(self):
        routemanager = self._get_currently_valid_routemanager()
        if routemanager is None:
            raise InternalStopWorkerException

        if self._db_wrapper.check_stop_quest(self.current_location.lat, self.current_location.lng):
            return False, False

        distance = get_distance_of_two_points_in_meters(float(self.last_location.lat),
                                                        float(
                                                            self.last_location.lng),
                                                        float(
                                                            self.current_location.lat),
                                                        float(self.current_location.lng))
        log.info('main: Moving %s meters to the next position' % distance)

        delay_used = 0
        log.debug("Getting time")
        speed = routemanager.settings.get("speed", 0)
        max_distance = routemanager.settings.get("max_distance", None)
        if (speed == 0 or
                (max_distance and 0 < max_distance < distance)
                or (self.last_location.lat == 0.0 and self.last_location.lng == 0.0)):
            log.info("main: Teleporting...")
            self._communicator.setLocation(
                self.current_location.lat, self.current_location.lng, 0)
            # the time we will take as a starting point to wait for data...
            cur_time = math.floor(time.time())

            delay_used = self._devicesettings.get('post_teleport_delay', 7)
            # Test for cooldown / teleported distance TODO: check this block...
            if self.first_round:
                delay_used = 3
                self.first_round = False
            else:
                if distance < 200:
                    delay_used = 5
                elif distance < 500:
                    delay_used = 15
                elif distance < 1000:
                    delay_used = 30
                elif distance > 1000:
                    delay_used = 80
                elif distance > 5000:
                    delay_used = 200
                elif distance > 10000:
                    delay_used = 400
                elif distance > 20000:
                    delay_used = 800
                log.info("Need more sleep after Teleport: %s seconds!" %
                         str(delay_used))
        else:
            log.info("main: Walking...")
            self._communicator.walkFromTo(self.last_location.lat, self.last_location.lng,
                                          self.current_location.lat, self.current_location.lng, speed)
            # the time we will take as a starting point to wait for data...
            cur_time = math.floor(time.time())
            delay_used = self._devicesettings.get('post_walk_delay', 7)
        log.info("Sleeping %s" % str(delay_used))
        time.sleep(float(delay_used))
        return cur_time, True

    def _post_move_location_routine(self, timestamp):
        if self._stop_worker_event.is_set():
            raise InternalStopWorkerException
        self._work_mutex.acquire()
        log.info("Processing Stop / Quest...")

        data_received = '-'

        reachedMainMenu = self._check_pogo_main_screen(5, True)
        if not reachedMainMenu:
            self._restart_pogo()

        log.info('Open Stop')
        data_received = self._open_pokestop()
        if data_received == 'Stop':
            self._handle_stop(data_received)
        log.debug("Releasing lock")
        self._work_mutex.release()

    def _start_pogo(self):
        pogo_topmost = self._communicator.isPogoTopmost()
        if pogo_topmost:
            return True

        if not self._communicator.isScreenOn():
            # TODO
            self._communicator.startApp("de.grennith.rgc.remotegpscontroller")
            log.warning("Turning screen on")
            self._communicator.turnScreenOn()
            time.sleep(self._devicesettings.get(
                "post_turn_screen_on_delay", 7))

        cur_time = time.time()
        start_result = False
        while not pogo_topmost:
            start_result = self._communicator.startApp(
                "com.nianticlabs.pokemongo")
            time.sleep(1)
            pogo_topmost = self._communicator.isPogoTopmost()
        reached_raidtab = False
        if start_result:
            log.warning("startPogo: Starting pogo...")
            time.sleep(self._devicesettings.get("post_pogo_start_delay", 60))
            self._last_known_state["lastPogoRestart"] = cur_time
            self._check_pogo_main_screen(15, True)
            reached_raidtab = True
        return reached_raidtab

    def _cleanup(self):
        pass

    def _clear_thread(self):
        log.info('Starting clear Quest Thread')
        while not self._stop_worker_event.is_set():
            # wait for event signal
            while not self._start_inventory_clear.is_set():
                time.sleep(0.5)
            if self.clear_thread_task > 0:
                self._work_mutex.acquire()
                try:
                    # TODO: less magic numbers?
                    time.sleep(1)
                    if self.clear_thread_task == 1:
                        log.info("Clearing box")
                        self.clear_box(self._delay_add)
                        self.clear_thread_task = 0
                    elif self.clear_thread_task == 2:
                        log.info("Clearing quest")
                        self._clear_quests(self._delay_add)
                        self.clear_thread_task = 0
                    time.sleep(1)
                    self._start_inventory_clear.clear()
                except WebsocketWorkerRemovedException:
                    log.error("Worker removed while clearing quest/box")
                    self._stop_worker_event.set()
                    return
                self._work_mutex.release()

    def clear_box(self, delayadd):
        log.info('Cleanup Box')
        x, y = self._resocalc.get_close_main_button_coords(self)[0], self._resocalc.get_close_main_button_coords(self)[
            1]
        self._communicator.click(int(x), int(y))
        time.sleep(1 + int(delayadd))
        x, y = self._resocalc.get_item_menu_coords(
            self)[0], self._resocalc.get_item_menu_coords(self)[1]
        self._communicator.click(int(x), int(y))
        time.sleep(1 + int(delayadd))
        data_received = '-'
        _data_err_counter = 0
        x, y = self._resocalc.get_delete_item_coords(
            self)[0], self._resocalc.get_delete_item_coords(self)[1]
        click_x1, click_x2, click_y = self._resocalc.get_swipe_item_amount(self)[0], \
            self._resocalc.get_swipe_item_amount(self)[1], \
            self._resocalc.get_swipe_item_amount(self)[2]
        to = 0
        while int(to) <= 3:

            self._communicator.click(int(x), int(y))
            time.sleep(.5 + int(delayadd))

            self._communicator.touchandhold(
                click_x1, click_y, click_x2, click_y)
            time.sleep(1)
            delx, dely = self._resocalc.get_confirm_delete_item_coords(self)[0], \
                self._resocalc.get_confirm_delete_item_coords(self)[1]
            curTime = time.time()
            self._communicator.click(int(delx), int(dely))

            data_received = self._wait_for_data(
                timestamp=curTime, proto_to_wait_for=4, timeout=15)

            if data_received is not None:
                if 'Clear' in data_received:
                    to += 1
                else:
                    self._communicator.backButton()
                    data_received = '-'
                    y += self._resocalc.get_next_item_coord(self)
            else:
                log.info('Click Gift / Raidpass')
                if not self._checkPogoButton():
                    self._checkPogoClose()
                data_received = '-'
                y += self._resocalc.get_next_item_coord(self)
                y += self._resocalc.get_next_item_coord(self)

        x, y = self._resocalc.get_close_main_button_coords(self)[0], self._resocalc.get_close_main_button_coords(self)[
            1]
        self._communicator.click(int(x), int(y))
        time.sleep(1 + int(delayadd))
        return True

    def _update_injection_settings(self):
        # we don't wanna do anything other than questscans, set ids_iv to null ;)
        self._mitm_mapper.update_latest(origin=self._id, timestamp=int(time.time()), key="ids_iv",
                                        values_dict=None)

        injected_settings = {}
        scanmode = "quests"
        injected_settings["scanmode"] = scanmode
        self._mitm_mapper.update_latest(origin=self._id, timestamp=int(time.time()), key="injected_settings",
                                        values_dict=injected_settings)

    def _open_pokestop(self):
        to = 0
        data_received = '-'
        while 'Stop' not in data_received and int(to) < 3:
            curTime = time.time()
            self._open_gym(self._delay_add)
            data_received = self._wait_for_data(
                timestamp=curTime, proto_to_wait_for=104, timeout=25)
            if data_received is not None:
                if 'Gym' in data_received:
                    log.info('Clicking GYM')
                    time.sleep(1)
                    x, y = self._resocalc.get_close_main_button_coords(self)[0], \
                        self._resocalc.get_close_main_button_coords(self)[1]
                    self._communicator.click(int(x), int(y))
                    time.sleep(1)
                    if not self._checkPogoButton():
                        self._checkPogoClose()
                    self._turn_map(self._delay_add)
                if 'Mon' in data_received:
                    time.sleep(1)
                    log.info('Clicking MON')
                    x, y = self._resocalc.get_leave_mon_coords(
                        self)[0], self._resocalc.get_leave_mon_coords(self)[1]
                    self._communicator.click(int(x), int(y))
                    time.sleep(.5)
                    if not self._checkPogoButton():
                        self._checkPogoClose()
                    self._turn_map(self._delay_add)
            if data_received is None:
                data_received = '-'

            to += 1
            time.sleep(0.5)
        return data_received

    def _handle_stop(self, data_received):
        to = 0
        while not 'Quest' in data_received and int(to) < 3:
            curTime = time.time()
            log.info('Spin Stop')
            self._spin_wheel(self._delay_add)
            data_received = self._wait_for_data(
                timestamp=curTime, proto_to_wait_for=101, timeout=20)
            if data_received is not None:

                if 'Box' in data_received:
                    log.error('Box is full ... Next round!')
                    self._close_gym(self._delay_add)
                    self.clear_thread_task = 1
                    break

                if 'Quest' in data_received:
                    log.info('Getting new Quest')
                    self._close_gym(self._delay_add)
                    self.clear_thread_task = 2
                    break

                if 'SB' in data_received or 'Time' in data_received:
                    log.error('Softban - waiting...')
                    self._close_gym(self._delay_add)
                    time.sleep(10)
                    self._open_pokestop()
                else:
                    log.error('Other Return: %s' % str(data_received))

                to += 1
                if to >= 3:
                    self._close_gym(self._delay_add)

            else:
                data_received = '-'
                log.error(
                    'Did not get any data ... Maybe already spinned or softban.')
                to += 1
                if to >= 3:
                    self._close_gym(self._delay_add)

    def _wait_for_data(self, timestamp, proto_to_wait_for=106, timeout=45):
        #timeout = self._devicesettings.get("mitm_wait_timeout", 45)
        max_data_err_counter = self._devicesettings.get(
            "max_data_err_counter", 60)
        log.info('Waiting for data after %s, error count is at %s' %
                 (str(timestamp), str(self.__data_error_counter)))
        data_requested = None
        while (data_requested is None and timestamp + timeout >= time.time()
               and self.__data_error_counter < max_data_err_counter):
            latest = self._mitm_mapper.request_latest(self._id)

            if latest is None:
                log.debug("Nothing received since MAD started")
                time.sleep(0.5)
                continue
            elif proto_to_wait_for not in latest:
                log.debug("No data linked to the requested proto since MAD started. Count: %s"
                          % str(self.__data_error_counter))
                self.__data_error_counter += 1
                time.sleep(0.5)
            elif 156 in latest:
                if latest[156]['timestamp'] >= timestamp:
                    # TODO: consider individual counters?
                    self.__data_error_counter = 0
                    self.__reboot_count = 0
                    self.__restart_count = 0
                    return 'Gym'
            elif 102 in latest:
                if latest[102]['timestamp'] >= timestamp:
                    self.__data_error_counter = 0
                    self.__reboot_count = 0
                    self.__restart_count = 0
                    return 'Mon'

            if proto_to_wait_for not in latest:
                log.debug("No data linked to the requested proto since MAD started. Count: %s"
                          % str(self.__data_error_counter))
                self.__data_error_counter += 1
                time.sleep(1)
            else:
                # requested proto received previously
                latest_proto = latest.get(proto_to_wait_for, None)
                current_routemanager = self._get_currently_valid_routemanager()
                if current_routemanager is None:
                    # we should be sleeping...
                    log.info("%s should be sleeping ;)" % str(self._id))
                    return None
                latest_timestamp = latest_proto.get("timestamp", 0)
                if latest_timestamp >= timestamp:
                    latest_data = latest_proto.get("values", None)
                    if 'items_awarded' in latest_data['payload']:
                        if latest_data['payload']['result'] == 1 and len(latest_data['payload']['items_awarded']) > 0:
                            self.__data_error_counter = 0
                            self.__reboot_count = 0
                            self.__restart_count = 0
                            return 'Quest'
                        elif (latest_data['payload']['result'] == 1
                              and len(latest_data['payload']['items_awarded']) == 0):
                            self.__data_error_counter = 0
                            self.__reboot_count = 0
                            self.__restart_count = 0
                            return 'Time'
                        elif latest_data['payload']['result'] == 2:
                            self.__data_error_counter = 0
                            self.__reboot_count = 0
                            self.__restart_count = 0
                            return 'SB'
                        elif latest_data['payload']['result'] == 4:
                            self.__data_error_counter = 0
                            self.__reboot_count = 0
                            self.__restart_count = 0
                            return 'Box'
                    if 'fort_id' in latest_data['payload']:
                        if latest_data['payload']['type'] == 1:
                            self.__data_error_counter = 0
                            self.__reboot_count = 0
                            self.__restart_count = 0
                            return 'Stop'
                    if 'inventory_delta' in latest_data['payload']:
                        if len(latest_data['payload']['inventory_delta']['inventory_items']) > 0:
                            self.__data_error_counter = 0
                            self.__reboot_count = 0
                            self.__restart_count = 0
                            return 'Clear'
                else:
                    log.debug("latest timestamp of proto %s (%s) is older than %s"
                              % (str(proto_to_wait_for), str(latest_timestamp), str(timestamp)))
                    # TODO: timeout error instead of data_error_counter? Differentiate timeout vs missing data (the
                    # TODO: latter indicates too high speeds for example
                    self.__data_error_counter += 1
                    time.sleep(0.5)
        if data_requested is not None:
            log.info('Got the data requested...')
            self.__reboot_count = 0
            self.__restart_count = 0
            self.__data_error_counter = 0
        else:
            log.warning("Timeout waiting for data")
            self.__reboot_count += 1
            self.__restart_count += 1
            if (self._devicesettings.get("reboot", False)
                    and self.reboot_count > self._devicesettings.get("reboot_thresh", 5)):
                log.error("Rebooting %s" % str(self._id))
                self._reboot()
                raise InternalStopWorkerException
            elif self.__data_error_counter >= max_data_err_counter and self.__restart_count > 5:
                self.__data_error_counter = 0
                self.__restart_count = 0
                self._restart_pogo(True)
            elif self.__data_error_counter >= max_data_err_counter and self.__restart_count <= 5:
                self.__data_error_counter = 0
        return data_requested
