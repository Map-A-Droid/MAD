import asyncio
import functools
import logging
import math
import time
from threading import Thread, Lock, Event, current_thread

from route.RouteManagerIV import RouteManagerIV
from utils.collections import Location
from utils.madGlobals import WebsocketWorkerRemovedException, MadGlobals
from utils.geo import get_distance_of_two_points_in_meters
from worker.WorkerBase import WorkerBase

log = logging.getLogger(__name__)


class WorkerMITM(WorkerBase):
    def __init__(self, args, id, last_known_state, websocket_handler, route_manager_daytime, route_manager_nighttime,
                 mitm_mapper, devicesettings, db_wrapper):
        WorkerBase.__init__(self, args, id, last_known_state, websocket_handler, route_manager_daytime,
                            route_manager_nighttime, devicesettings, db_wrapper=db_wrapper, NoOcr=True)

        self.id = id
        self._work_mutex = Lock()
        self._run_warning_thread_event = Event()
        self._locationCount = 0
        self._mitm_mapper = mitm_mapper
        # self.thread_pool = ThreadPool(processes=4)
        self.loop = None
        self.loop_started = Event()
        self.loop_tid = None
        # TODO: own InjectionSettings class
        self._injection_settings = {}
        self.__update_injection_settings()

    def __update_injection_settings(self):
        injected_settings = {}
        scanmode = "nothing"
        if MadGlobals.sleep and self._route_manager_nighttime is None:
            # worker has to sleep, just empty out the settings...
            self._mitm_mapper.update_latest(origin=self.id, timestamp=int(time.time()), key="ids_iv",
                                            values_dict={})
            scanmode = "nothing"
        else:
            if MadGlobals.sleep:
                routemanager = self._route_manager_nighttime
            else:
                routemanager = self._route_manager_daytime

            ids_iv = routemanager.settings.get("mon_ids_iv", None)
            if routemanager.mode == "mon_mitm":
                scanmode = "mons"
            elif routemanager.mode == "raids_mitm":
                scanmode = "raids"
            elif routemanager.mode == "iv_mitm" and isinstance(routemanager, RouteManagerIV):
                scanmode = "ivs"
                ids_iv = routemanager.encounter_ids_left
            self._mitm_mapper.update_latest(origin=self.id, timestamp=int(time.time()), key="ids_iv",
                                            values_dict=ids_iv)
        injected_settings["scanmode"] = scanmode
        self._mitm_mapper.update_latest(origin=self.id, timestamp=int(time.time()), key="injected_settings",
                                        values_dict=injected_settings)

    def __start_asyncio_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop_tid = current_thread()
        self.loop.call_soon(self.loop_started.set)
        self.loop.run_forever()

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
            return f()  # We can call directly if we're not going between threads.
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
            time.sleep(self._devicesettings.get("post_turn_screen_on_delay", 7))

        cur_time = time.time()
        start_result = False
        while not pogo_topmost:
            start_result = self._communicator.startApp("com.nianticlabs.pokemongo")
            time.sleep(1)
            pogo_topmost = self._communicator.isPogoTopmost()
        reached_raidtab = False
        if start_result:
            log.warning("startPogo: Starting pogo...")
            time.sleep(self._devicesettings.get("post_pogo_start_delay", 60))
            self._last_known_state["lastPogoRestart"] = cur_time

            # let's handle the login and stuff
            reached_raidtab = True

        return reached_raidtab

    # TODO: update state...
    def _main_work_thread(self):
        current_thread().name = self.id
        log.info("MITM worker starting")
        _data_err_counter, data_error_counter = 0, 0
        # first check if pogo is running etc etc

        t_asyncio_loop = Thread(name='mitm_asyncio_' + self.id, target=self.__start_asyncio_loop)
        t_asyncio_loop.daemon = True
        t_asyncio_loop.start()

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

        currentLocation = self._last_known_state.get("last_location", None)
        if currentLocation is None:
            currentLocation = Location(0.0, 0.0)
        lastLocation = None
        while not self._stop_worker_event.isSet():
            while MadGlobals.sleep and self._route_manager_nighttime is None:
                time.sleep(1)
            log.debug("Worker: acquiring lock for restart check")
            self._work_mutex.acquire()
            log.debug("Worker: acquired lock")

            # check if pogo is topmost and start if necessary
            try:
                log.debug("Calling _start_pogo routine to check if pogo is topmost")
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
                    log.error("scanned " + str(self._devicesettings.get("restart_pogo", 80)) + " locations, restarting pogo")
                    self._restartPogo()
                    self._locationCount = 0
            self._work_mutex.release()
            log.debug("Worker: lock released")

            # TODO: consider adding runWarningThreadEvent.set()
            lastLocation = currentLocation
            self._last_known_state["last_location"] = lastLocation

            log.debug("Requesting next location from routemanager")
            # requesting a location is blocking (iv_mitm will wait for a prioQ item), we really need to clean
            # the workers up...
            if MadGlobals.sleep and self._route_manager_nighttime is not None:
                if self._route_manager_nighttime.mode not in ["iv_mitm", "raids_mitm", "mon_mitm"]:
                    break
                currentLocation = self._route_manager_nighttime.get_next_location()
                settings = self._route_manager_nighttime.settings
            elif MadGlobals.sleep:
                # skip to top while loop to get to sleep loop
                continue
            else:
                if self._route_manager_daytime.mode not in ["iv_mitm", "raids_mitm", "mon_mitm"]:
                    break
                currentLocation = self._route_manager_daytime.get_next_location()
                settings = self._route_manager_daytime.settings

            self.__update_injection_settings()

            # TODO: set position... needs to be adjust for multidevice

            log.debug("Updating .position file")
            with open(self.id + '.position', 'w') as outfile:
                outfile.write(str(currentLocation.lat)+", "+str(currentLocation.lng))

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
            if MadGlobals.sleep:
                speed = self._route_manager_nighttime.settings.get("speed", 0)
            else:
                speed = self._route_manager_daytime.settings.get("speed", 0)
            if (speed == 0 or
                    (settings['max_distance'] and 0 < settings['max_distance'] < distance)
                    or (lastLocation.lat == 0.0 and lastLocation.lng == 0.0)):
                log.info("main: Teleporting...")
                try:
                    self._communicator.setLocation(currentLocation.lat, currentLocation.lng, 0)
                    curTime = math.floor(time.time())  # the time we will take as a starting point to wait for data...
                except WebsocketWorkerRemovedException:
                    log.error("Timeout setting location for %s" % str(self.id))
                    self._stop_worker_event.set()
                    return
                delayUsed = self._devicesettings.get('post_teleport_delay', 7)
                # Test for cooldown / teleported distance TODO: check this block...
                if self._devicesettings.get('cool_down_sleep', False):
                    if distance > 2500:
                        delayUsed = 8
                    elif distance > 5000:
                        delayUsed = 10
                    elif distance > 10000:
                        delayUsed = 15
                    log.info("Need more sleep after Teleport: %s seconds!" % str(delayUsed))
                    # curTime = math.floor(time.time())  # the time we will take as a starting point to wait for data...

                if 0 < self._devicesettings.get('walk_after_teleport_distance', 0) < distance:
                    toWalk = get_distance_of_two_points_in_meters(float(currentLocation.lat), float(currentLocation.lng),
                                                                  float(currentLocation.lat) + 0.0001,
                                                                  float(currentLocation.lng) + 0.0001)
                    log.info("Walking a bit: %s" % str(toWalk))
                    try:
                        time.sleep(0.3)
                        self._communicator.walkFromTo(currentLocation.lat, currentLocation.lng,
                                                      currentLocation.lat + 0.0001, currentLocation.lng + 0.0001, 11)
                        log.debug("Walking back")
                        time.sleep(0.3)
                        self._communicator.walkFromTo(currentLocation.lat + 0.0001, currentLocation.lng + 0.0001,
                                                      currentLocation.lat, currentLocation.lng, 11)
                    except WebsocketWorkerRemovedException:
                        log.error("Timeout setting location for %s" % str(self.id))
                        self._stop_worker_event.set()
                        return
                    log.debug("Done walking")
            else:
                log.info("main: Walking...")
                try:
                    self._communicator.walkFromTo(lastLocation.lat, lastLocation.lng,
                                                  currentLocation.lat, currentLocation.lng, speed)
                    curTime = math.floor(time.time())  # the time we will take as a starting point to wait for data...
                except WebsocketWorkerRemovedException:
                    log.error("Timeout setting location for %s" % str(self.id))
                    self._stop_worker_event.set()
                    return
                delayUsed = self._devicesettings.get('post_walk_delay', 7)
            log.info("Sleeping %s" % str(delayUsed))
            time.sleep(float(delayUsed))

            if self._applicationArgs.last_scanned:
                log.info('main: Set new scannedlocation in Database')
                # self.update_scanned_location(currentLocation.lat, currentLocation.lng, curTime)
                self.__add_task_to_loop(self.update_scanned_location(currentLocation.lat, currentLocation.lng, curTime))

            log.debug("Acquiring lock")
            self._work_mutex.acquire()
            log.debug("Waiting for data to be received...")
            data_received, data_error_counter = self.wait_for_data(data_err_counter=_data_err_counter,
                                                                   timestamp=curTime)
            _data_err_counter = data_error_counter
            log.debug("Releasing lock")
            self._work_mutex.release()
            log.debug("Worker %s done, next iteration" % str(self.id))

        self.stop_worker()
        self.loop.stop()

    async def update_scanned_location(self, latitude, longitude, timestamp):
        try:
            self._db_wrapper.set_scanned_location(str(latitude), str(longitude), str(timestamp))
        except Exception as e:
            log.error("Failed updating scanned location: %s" % str(e))
            return

    def wait_for_data(self, timestamp, proto_to_wait_for=106, data_err_counter=0):
        timeout = self._devicesettings.get("mitm_wait_timeout", 45)

        log.info('Waiting for data after %s' % str(timestamp))
        data_requested = None
        while data_requested is None and timestamp + timeout >= time.time():
            # let's check for new data...
            # log.info('Requesting latest...')
            latest = self._mitm_mapper.request_latest(self.id)  
            if latest is None:
                log.warning('Nothing received from client since MAD started...')
                # we did not get anything from that client at all, let's check again in a sec
                time.sleep(0.5)
                continue
            elif proto_to_wait_for not in latest:
                log.warning(
                    'Did not get any of the requested data... (count: %s)' %
                    (str(data_err_counter)))
                data_err_counter += 1

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

                current_mode = daytime_mode if not MadGlobals.sleep else nighttime_mode

                if latest_timestamp >= timestamp:
                    if current_mode == 'mon_mitm' or current_mode == "iv_mitm":
                        data_err_counter = 0
                        for data_extract in data['payload']['cells']:
                            for WP in data_extract['wild_pokemon']:
                                # TODO: teach Prio Q / Clusterer to hold additional data such as mon/encounter IDs
                                if WP['spawnpoint_id']:
                                    data_requested = data
                                    break
                            if data_requested is None:
                                for catchable_pokemon in data_extract['catchable_pokemon']:
                                    if catchable_pokemon['spawn_id']:
                                        data_requested = data
                        if data_requested is None:
                            log.debug("No spawnpoints in data requested")
                    elif current_mode == 'raids_mitm':
                        for data_extract in data['payload']['cells']:
                            for forts in data_extract['forts']:
                                if forts['id']:
                                    data_requested = data
                        if data_requested is None:
                            log.debug("No forts in data received")
                    else:
                        log.warning("No mode specified to wait for")
                        data_err_counter += 1
                        time.sleep(0.5)
                else:
                    log.debug("latest timestamp of proto %s (%s) is older than %s"
                              % (str(proto_to_wait_for), str(latest_timestamp), str(timestamp)))
                    data_err_counter += 1
                    time.sleep(0.5)

            max_data_err_counter = 60
            if self._devicesettings is not None:
                max_data_err_counter = self._devicesettings.get("max_data_err_counter", 60)
            if data_err_counter >= int(max_data_err_counter):
                log.warning("Errorcounter reached restart thresh, restarting pogo")
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
