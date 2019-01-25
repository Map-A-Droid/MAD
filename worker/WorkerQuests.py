import asyncio
import functools
import logging
import math
import time
from threading import Event, Lock, Thread, current_thread

from utils.collections import Location
from utils.geo import get_distance_of_two_points_in_meters
from utils.resolution import Resocalculator
from worker.WorkerBase import WorkerBase

log = logging.getLogger(__name__)


class WorkerQuests(WorkerBase):
    def __init__(self, args, id, last_known_state, websocket_handler, route_manager_daytime, route_manager_nighttime,
                 mitm_mapper, devicesettings, db_wrapper, timer):

        self._resocalc = Resocalculator
        WorkerBase.__init__(self, args, id, last_known_state, websocket_handler, route_manager_daytime,
                            route_manager_nighttime, devicesettings, db_wrapper=db_wrapper, NoOcr=False, resocalc=self._resocalc)

        self.id = id
        self._work_mutex = Lock()
        self._run_warning_thread_event = Event()
        self._locationCount = 0
        self._mitm_mapper = mitm_mapper
        self._timer = timer
        # self.thread_pool = ThreadPool(processes=4)
        self.loop = None
        self.loop_started = Event()
        self.loop_tid = None
        # TODO: own InjectionSettings class
        self._injection_settings = {}
        self.__update_injection_settings()
        self._screen_x = 0
        self._screen_y = 0
        self._clear_box = False
        self._clear_quest = False
        self._delayadd = 0

    def __update_injection_settings(self):
        # we don't wanna do anything other than questscans, set ids_iv to null ;)
        self._mitm_mapper.update_latest(origin=self.id, timestamp=int(time.time()), key="ids_iv",
                                        values_dict=None)

        injected_settings = {}
        scanmode = "quests"
        injected_settings["scanmode"] = scanmode
        self._mitm_mapper.update_latest(origin=self.id, timestamp=int(time.time()), key="injected_settings",
                                        values_dict=injected_settings)

    def __start_asyncio_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop_tid = current_thread()
        self.loop.call_soon(self.loop_started.set)
        self.loop.run_forever()

    def get_screen_size(self):
        screen = self._communicator.getscreensize().split(' ')
        self._screen_x = screen[0]
        self._screen_y = screen[1]
        log.debug('Get Screensize of %s: X: %s, Y: %s' %
                  (str(self.id), str(self._screen_x), str(self._screen_y)))
        self._resocalc.get_x_y_ratio(self, self._screen_x, self._screen_y)

    def __add_task_to_loop(self, coro):
        # def _async_add(func, fut):
        #     try:
        #         ret = func()
        #         fut.set_result(ret)
        #     except Exception as e:
        #         fut.set_exception(e)
        #
        # f = functools.partial(asyncio.async, coro, loop=self.loop)
        f = functools.partial(self.loop.create_task, coro)
        if current_thread() == self.loop_tid:
            # We can call directly if we're not going between threads.
            return f()
        else:
            # We're in a non-event loop thread so we use a Future
            # to get the task from the event loop thread once
            # it's ready.
            # f = functools.partial(self.loop.create_task, coro)
            return self.loop.call_soon_threadsafe(f)
            # fut = Future()
            # self.loop.call_soon_threadsafe(_async_add, f, fut)
            # return fut.result()

    def __stop_loop(self):
        self.loop.call_soon_threadsafe(self.loop.stop)

    def _start_pogo(self):
        pogo_topmost = self._communicator.isPogoTopmost()
        if pogo_topmost:
            return True

        if not self._communicator.isScreenOn():
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
            self._checkPogoMainScreen(15, True)
            reached_raidtab = True
        return reached_raidtab

    # TODO: update state...
    def _main_work_thread(self):
        current_thread().name = self.id
        log.info("Quests worker starting")
        _data_err_counter, data_error_counter = 0, 0
        firstround = True

        t_asyncio_loop = Thread(name='mitm_asyncio_' +
                                self.id, target=self.__start_asyncio_loop)
        t_asyncio_loop.daemon = True
        t_asyncio_loop.start()

        clearThread = Thread(name='clearThread%s' %
                             self.id, target=self._clear_thread)
        clearThread.daemon = True
        clearThread.start()

        self.get_screen_size()
        self._delayadd = int(self._devicesettings.get("vps_delay", 0))

        self._work_mutex.acquire()
        try:
            self._start_pogo()
        except WebsocketWorkerRemovedException:
            log.error("Timeout during init of worker %s" % str(self.id))
            self._stop_worker_event.set()
            self._work_mutex.release()
            return
        self._work_mutex.release()

        self.loop_started.wait()

        reachedMainMenu = self._checkPogoMainScreen(15, True)
        if not reachedMainMenu:
            self._restartPogo()

        currentLocation = self._last_known_state.get("last_location", None)
        if currentLocation is None:
            currentLocation = Location(0.0, 0.0)
        lastLocation = None

        while not self._stop_worker_event.isSet():
            while self._timer.get_switch() and self._route_manager_nighttime is None:
                time.sleep(1)
            log.debug("Worker: acquiring lock for restart check")
            self._work_mutex.acquire()
            log.debug("Worker: acquired lock")

            # check if pogo is topmost and start if necessary
            try:
                log.debug(
                    "Calling _start_pogo routine to check if pogo is topmost")
                self._start_pogo()
            except WebsocketWorkerRemovedException:
                log.error("Timeout starting pogo on %s" % str(self.id))
                self._stop_worker_event.set()
                self._work_mutex.release()
                return

            log.debug("Checking if we need to restart pogo")
            # Restart pogo every now and then...
            if self._devicesettings.get("restart_pogo", 80) > 0:
                # log.debug("main: Current time - lastPogoRestart: %s" % str(curTime - lastPogoRestart))
                # if curTime - lastPogoRestart >= (args.restart_pogo * 60):
                self._locationCount += 1
                if self._locationCount > self._devicesettings.get("restart_pogo", 80):
                    log.error("scanned " + str(self._devicesettings.get(
                        "restart_pogo", 80)) + " locations, restarting pogo")
                    self._restartPogo()
                    self._locationCount = 0
            self._work_mutex.release()
            log.debug("Worker: lock released")

            # TODO: consider adding runWarningThreadEvent.set()
            lastLocation = currentLocation
            self._last_known_state["last_location"] = lastLocation

            log.debug("Requesting next location from routemanager")
            if self._timer.get_switch() and self._route_manager_nighttime is not None:
                currentLocation = self._route_manager_nighttime.get_next_location()
                settings = self._route_manager_nighttime.settings
                while self._db_wrapper.check_stop_quest(currentLocation.lat, currentLocation.lng):
                    self._route_manager_nighttime.del_from_route()
                    currentLocation = self._route_manager_nighttime.get_next_location()
            elif self._timer.get_switch():
                # skip to top while loop to get to sleep loop
                continue
            else:
                currentLocation = self._route_manager_daytime.get_next_location()
                settings = self._route_manager_daytime.settings
                while self._db_wrapper.check_stop_quest(currentLocation.lat, currentLocation.lng):
                    self._route_manager_daytime.del_from_route()
                    currentLocation = self._route_manager_daytime.get_next_location()

            self.__update_injection_settings()

            # TODO: set position... needs to be adjust for multidevice

            log.debug("Updating .position file")
            with open(self.id + '.position', 'w') as outfile:
                outfile.write(str(currentLocation.lat) +
                              ", "+str(currentLocation.lng))

            log.debug("main: next stop: %s" % (str(currentLocation)))
            log.debug('main: LastLat: %s, LastLng: %s, CurLat: %s, CurLng: %s' %
                      (lastLocation.lat, lastLocation.lng,
                       currentLocation.lat, currentLocation.lng))
            # get the distance from our current position (last) to the next gym (cur)
            distance = get_distance_of_two_points_in_meters(float(lastLocation.lat), float(lastLocation.lng),
                                                            float(currentLocation.lat), float(currentLocation.lng))
            log.info('main: Moving %s meters to the next position' % distance)
            delayUsed = 0
            log.debug("Getting time")
            if self._timer.get_switch():
                speed = self._route_manager_nighttime.settings.get("speed", 0)
            else:
                speed = self._route_manager_daytime.settings.get("speed", 0)
            if (speed == 0 or
                    (settings['max_distance'] and 0 <
                     settings['max_distance'] < distance)
                    or (lastLocation.lat == 0.0 and lastLocation.lng == 0.0)):
                log.info("main: Teleporting...")
                # TODO: catch exception...
                try:
                    self._communicator.setLocation(
                        currentLocation.lat, currentLocation.lng, 0)
                    # the time we will take as a starting point to wait for data...
                    curTime = math.floor(time.time())
                except WebsocketWorkerRemovedException:
                    log.error("Timeout setting location for %s" % str(self.id))
                    self._stop_worker_event.set()
                    return
                delayUsed = self._devicesettings.get('post_teleport_delay', 7)
                # Test for cooldown / teleported distance TODO: check this block...
                if firstround:
                    delayUsed = 3
                    firstround = False
                else:
                    if distance < 200:
                        delayUsed = 5
                    elif distance < 500:
                        delayUsed = 15
                    elif distance < 1000:
                        delayUsed = 30
                    elif distance > 1000:
                        delayUsed = 80
                    elif distance > 5000:
                        delayUsed = 200
                    elif distance > 10000:
                        delayUsed = 400
                    elif distance > 20000:
                        delayUsed = 800
                    log.info("Need more sleep after Teleport: %s seconds!" %
                             str(delayUsed))
                    # curTime = math.floor(time.time())  # the time we will take as a starting point to wait for data...
            else:
                log.info("main: Walking...")
                try:
                    self._communicator.walkFromTo(lastLocation.lat, lastLocation.lng,
                                                  currentLocation.lat, currentLocation.lng, speed)
                    # the time we will take as a starting point to wait for data...
                    curTime = math.floor(time.time())
                except WebsocketWorkerRemovedException:
                    log.error("Timeout setting location for %s" % str(self.id))
                    self._stop_worker_event.set()
                    return
                delayUsed = 0
            log.info("Sleeping %s" % str(delayUsed))
            time.sleep(float(delayUsed))

            if self._applicationArgs.last_scanned:
                log.info('main: Set new scannedlocation in Database')
                # self.update_scanned_location(currentLocation.lat, currentLocation.lng, curTime)
                self.__add_task_to_loop(self.update_scanned_location(
                    currentLocation.lat, currentLocation.lng, curTime))

            log.debug("Acquiring lock")
            self._work_mutex.acquire()
            log.debug("Processing Stop / Quest...")

            to = 0
            data_received = '-'

            while self._clear_quest or self._clear_box:
                time.sleep(1)

            reachedMainMenu = self._checkPogoMainScreen(15, True)
            if not reachedMainMenu:
                self._restartPogo()

            while not 'Stop' in data_received and int(to) < 3:
                curTime = time.time()
                self._open_gym(self._delayadd)
                data_received, data_error_counter = self.wait_for_data(data_err_counter=_data_err_counter,
                                                                       timestamp=curTime, proto_to_wait_for=104, timeout=25)
                _data_err_counter = data_error_counter
                if data_received is not None:
                    if 'Gym' in data_received:
                        log.debug('Clicking GYM')
                        x, y = self._resocalc.get_close_main_button_coords(
                            self)[0], self._resocalc.get_close_main_button_coords(self)[1]
                        self._communicator.click(int(x), int(y))
                        time.sleep(2)
                        self._turn_map(self._delayadd)
                    if 'Mon' in data_received:
                        time.sleep(2)
                        log.debug('Clicking MON')
                        x, y = self._resocalc.get_leave_mon_coords(
                            self)[0], self._resocalc.get_leave_mon_coords(self)[1]
                        self._communicator.click(int(x), int(y))
                        time.sleep(.5)
                        self._turn_map(self._delayadd)
                if data_received is None:
                    data_received = '-'

                to += 1
                time.sleep(0.5)

            to = 0

            if 'Stop' in data_received:
                while not 'Quest' in data_received and int(to) < 3:
                    curTime = time.time()
                    self._spin_wheel(self._delayadd)
                    data_received, data_error_counter = self.wait_for_data(data_err_counter=_data_err_counter,
                                                                           timestamp=curTime, proto_to_wait_for=101, timeout=20)
                    _data_err_counter = data_error_counter

                    if data_received is not None:

                        if 'Box' in data_received:
                            log.error('Box is full ... Next round!')
                            self._close_gym(self._delayadd)
                            to = 3
                            self._clear_box = True
                            roundcount = 0
                            break

                        if 'Quest' in data_received:
                            self._close_gym(self._delayadd)
                            self._clear_quest = True
                            break

                        if 'SB' in data_received:
                            log.error('Softban - waiting...')
                            time.sleep(10)

                        to += 1
                        if to == 3:
                            self._close_gym(self._delayadd)

                    else:
                        data_received = '-'
                        log.error(
                            'Did not get any data ... Maybe already spinned or softban.')
                        to += 1
                        if to == 3:
                            self._close_gym(self._delayadd)

            log.debug("Releasing lock")
            self._work_mutex.release()
            log.debug("Worker %s done, next iteration" % str(self.id))

        t_asyncio_loop.join()

    async def update_scanned_location(self, latitude, longitude, timestamp):
        try:
            self._db_wrapper.set_scanned_location(
                str(latitude), str(longitude), str(timestamp))
        except Exception as e:
            log.error("Failed updating scanned location: %s" % str(e))
            return

    def wait_for_data(self, timestamp, proto_to_wait_for=106, data_err_counter=0, timeout=45):
        #timeout = self._devicesettings.get("mitm_wait_timeout", 45)
        log.info('Waiting for  data...')
        data_requested = None
        while data_requested is None and timestamp + timeout >= time.time():
            # let's check for new data...
            # log.info('Requesting latest...')
            latest = self._mitm_mapper.request_latest(self.id)

            if latest is None:
                log.warning(
                    'Nothing received from client since MAD started...')
                # we did not get anything from that client at all, let's check again in a sec
                time.sleep(0.5)
                continue
            elif proto_to_wait_for not in latest:
                log.warning(
                    'Did not get any of the requested data... (count: %s)' %
                    (str(data_err_counter)))
                data_err_counter += 1
                if 156 in latest:
                    if latest[156]['timestamp'] >= timestamp:
                        data_err_counter = 0
                        return 'Gym', data_err_counter
                if 102 in latest:
                    if latest[102]['timestamp'] >= timestamp:
                        data_err_counter = 0
                        return 'Mon', data_err_counter
                time.sleep(0.5)
            else:
                # log.debug('latest contains data...')
                data = latest[proto_to_wait_for]['values']
                latest_timestamp = latest[proto_to_wait_for]['timestamp']
                if self._route_manager_nighttime is not None:
                    nighttime_mode = self._route_manager_nighttime.mode
                else:
                    nighttime_mode = None
                daytime_mode = self._route_manager_daytime.mode

                current_mode = daytime_mode if not self._timer.get_switch() else nighttime_mode

                if latest_timestamp >= timestamp:

                    if 'items_awarded' in data['payload']:
                        if data['payload']['result'] == 1 and len(data['payload']['items_awarded']) > 0:
                            data_err_counter = 0
                            return 'Quest', data_err_counter
                        elif data['payload']['result'] == 1 and len(data['payload']['items_awarded']) == 0:
                            data_err_counter = 0
                            return 'Time', data_err_counter
                        elif data['payload']['result'] == 2:
                            data_err_counter = 0
                            return 'SB', data_err_counter
                        elif data['payload']['result'] == 4:
                            data_err_counter = 0
                            return 'Box', data_err_counter

                    if 156 in latest:
                        if latest[156]['timestamp'] >= timestamp:
                            data_err_counter = 0
                            return 'Gym', data_err_counter
                    if 102 in latest:
                        if latest[102]['timestamp'] >= timestamp:
                            data_err_counter = 0
                            return 'Mon', data_err_counter

                    if 'fort_id' in data['payload']:
                        if data['payload']['type'] == 1:
                            data_err_counter = 0
                            return 'Stop', data_err_counter

                    if 'inventory_delta' in data['payload']:
                        if len(data['payload']['inventory_delta']['inventory_items']) > 0:
                            data_err_counter = 0
                            return 'Clear', data_err_counter
                else:
                    log.debug("latest timestamp of proto %s (%s) is older than %s"
                              % (str(proto_to_wait_for), str(latest_timestamp), str(timestamp)))
                    if 156 in latest:
                        if latest[156]['timestamp'] >= timestamp:
                            data_err_counter = 0
                            return 'Gym', data_err_counter
                    if 102 in latest:
                        if latest[102]['timestamp'] >= timestamp:
                            data_err_counter = 0
                            return 'Mon', data_err_counter
                    data_err_counter += 1
                    time.sleep(0.5)

            max_data_err_counter = 60
            if self._devicesettings is not None:
                max_data_err_counter = self._devicesettings.get(
                    "max_data_err_counter", 60)
            if data_err_counter >= int(max_data_err_counter):
                log.warning(
                    "Errorcounter reached restart thresh, restarting pogo")
                self._restartPogoDroid()
                self._restartPogo(False)
                return None, 0
            elif data_requested is None:
                # log.debug('data_requested still None...')
                time.sleep(0.5)

        if data_requested is not None:
            log.debug('Got the data requested...')
            data_err_counter = 0
        else:
            log.warning("Timeout waiting for data")
        return data_requested, data_err_counter

    def clear_box(self, delayadd):
        log.info('Cleanup Box')
        x, y = self._resocalc.get_close_main_button_coords(
            self)[0], self._resocalc.get_close_main_button_coords(self)[1]
        self._communicator.click(int(x), int(y))
        time.sleep(.5 + int(delayadd))
        x, y = self._resocalc.get_item_menu_coords(
            self)[0], self._resocalc.get_item_menu_coords(self)[1]
        self._communicator.click(int(x), int(y))
        time.sleep(1 + int(delayadd))
        data_received = '-'
        _data_err_counter = 0
        x, y = self._resocalc.get_delete_item_coords(
            self)[0], self._resocalc.get_delete_item_coords(self)[1]
        click_x1, click_x2, click_y = self._resocalc.get_swipe_item_amount(
            self)[0], self._resocalc.get_swipe_item_amount(self)[1], self._resocalc.get_swipe_item_amount(self)[2]
        to = 0
        while int(to) <= 5:

            self._communicator.click(int(x), int(y))
            time.sleep(.5 + int(delayadd))

            self._communicator.touchandhold(
                click_x1, click_y, click_x2, click_y)
            time.sleep(3)
            delx, dely = self._resocalc.get_confirm_delete_item_coords(
                self)[0], self._resocalc.get_confirm_delete_item_coords(self)[1]
            curTime = time.time()
            self._communicator.click(int(delx), int(dely))

            data_received, data_error_counter = self.wait_for_data(data_err_counter=_data_err_counter,
                                                                   timestamp=curTime, proto_to_wait_for=4, timeout=10)
            _data_err_counter = data_error_counter

            if data_received is not None:
                if 'Clear' in data_received:
                    to += 1
                else:
                    self._communicator.backButton()
                    data_received = '-'
                    y += self._resocalc.get_next_item_coord(self)
            else:
                if not self._checkPogoButton():
                    self._checkPogoClose()
                data_received = '-'
                y += self._resocalc.get_next_item_coord(self)

        x, y = self._resocalc.get_close_main_button_coords(
            self)[0], self._resocalc.get_close_main_button_coords(self)[1]
        self._communicator.click(int(x), int(y))
        time.sleep(1 + int(delayadd))
        return True

    def _clear_thread(self):
        log.info('Starting clear Quest Thread')
        while True:
            if self._clear_quest:
                log.info('Clear Quest')
                time.sleep(2)
                self._clear_quests(self._delayadd)
                time.sleep(2)
                self._clear_quest = False
            if self._clear_box:
                log.info('Clear Box')
                time.sleep(2)
                self.clear_box(self._delayadd)
                time.sleep(2)
                self._clear_box = False
            time.sleep(2)
