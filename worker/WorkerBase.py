import asyncio
import collections
import functools
import json
import logging
import os
import time
from abc import ABC, abstractmethod
from multiprocessing.pool import ThreadPool
from threading import Event, Lock, Thread, current_thread

from utils.hamming import hamming_distance as hamming_dist
from utils.madGlobals import (InternalStopWorkerException,
                              WebsocketWorkerRemovedException,
                              WebsocketWorkerTimeoutException)
from utils.resolution import Resocalculator
from websocket.communicator import Communicator

Location = collections.namedtuple('Location', ['lat', 'lng'])

log = logging.getLogger(__name__)


class WorkerBase(ABC):
    def __init__(self, args, id, last_known_state, websocket_handler, route_manager_daytime,
                 route_manager_nighttime, devicesettings, db_wrapper, timer, NoOcr=False):
        # self.thread_pool = ThreadPool(processes=2)
        self._route_manager_daytime = route_manager_daytime
        self._route_manager_nighttime = route_manager_nighttime
        self._websocket_handler = websocket_handler
        self._communicator = Communicator(
            websocket_handler, id, args.websocket_command_timeout)
        self._id = id
        self._applicationArgs = args
        self._last_known_state = last_known_state
        self._work_mutex = Lock()
        self.loop = None
        self.loop_started = Event()
        self.loop_tid = None
        self._location_count = 0
        self.reboot_count = 0
        self._timer = timer

        self._lastScreenshotTaken = 0
        self._stop_worker_event = Event()
        self._db_wrapper = db_wrapper
        self._redErrorCount = 0
        self._lastScreenHash = None
        self._lastScreenHashCount = 0
        self._devicesettings = devicesettings
        self._resocalc = Resocalculator
        self._screen_x = 0
        self._screen_y = 0

        self.current_location = self._last_known_state.get(
            "last_location", None)
        if self.current_location is None:
            self.current_location = Location(0.0, 0.0)
        self.last_location = Location(0.0, 0.0)

        if not NoOcr:
            from ocr.pogoWindows import PogoWindows
            self._pogoWindowManager = PogoWindows(
                self._communicator, args.temp_path)

    @abstractmethod
    def _pre_work_loop(self):
        """
        Work to be done before the main while true work-loop
        Start off asyncio loops etc in here
        :return:
        """
        pass

    @abstractmethod
    def _health_check(self):
        """
        Health check before a location is grabbed. Internally, a self._start_pogo call is already executed since
        that usually includes a topmost check
        :return:
        """
        pass

    @abstractmethod
    def _pre_location_update(self):
        """
        Override to run stuff like update injections settings in MITM worker
        Runs before walk/teleport to the location previously grabbed
        :return:
        """
        pass

    @abstractmethod
    def _move_to_location(self):
        """
        Location has previously been grabbed, the overriden function will be called.
        You may teleport or walk by your choosing
        Any post walk/teleport delays/sleeps have to be run in the derived, override method
        :return:
        """
        pass

    @abstractmethod
    def _post_move_location_routine(self, timestamp):
        """
        Routine called after having moved to a new location. MITM worker e.g. has to wait_for_data
        :param timestamp:
        :return:
        """

    @abstractmethod
    def _start_pogo(self):
        """
        Routine to start pogo.
        Return the state as a boolean do indicate a successful start
        :return:
        """
        pass

    @abstractmethod
    def _cleanup(self):
        """
        Cleanup any threads you started in derived classes etc
        self.stop_worker() and self.loop.stop() will be called afterwards
        :return:
        """

    @abstractmethod
    def _valid_modes(self):
        """
        Return a list of valid modes for the health checks
        :return:
        """

    def _start_asyncio_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop_tid = current_thread()
        self.loop.call_soon(self.loop_started.set)
        self.loop.run_forever()

    def _add_task_to_loop(self, coro):
        f = functools.partial(self.loop.create_task, coro)
        if current_thread() == self.loop_tid:
            # We can call directly if we're not going between threads.
            return f()
        else:
            # We're in a non-event loop thread so we use a Future
            # to get the task from the event loop thread once
            # it's ready.
            return self.loop.call_soon_threadsafe(f)

    def start_worker(self):
        # async_result = self.thread_pool.apply_async(self._main_work_thread, ())
        t_main_work = Thread(target=self._main_work_thread)
        t_main_work.daemon = False
        t_main_work.start()
        # do some other stuff in the main process
        while not self._stop_worker_event.isSet():
            time.sleep(1)
        t_main_work.join()
        # async_result.get()
        return self._last_known_state

    def stop_worker(self):
        self._stop_worker_event.set()
        log.warning("Worker %s stop called" % str(self._id))

    def _internal_pre_work(self):
        current_thread().name = self._id

        self._work_mutex.acquire()
        try:
            self._turn_screen_on_and_start_pogo()
        except WebsocketWorkerRemovedException:
            log.error("Timeout during init of worker %s" % str(self._id))
            # no cleanup required here? TODO: signal websocket server somehow
            self._stop_worker_event.set()
            return
        self._work_mutex.release()

        t_asyncio_loop = Thread(
            name=str(self._id) + '_asyncio_' + self._id, target=self._start_asyncio_loop)
        t_asyncio_loop.daemon = True
        t_asyncio_loop.start()

        self.loop_started.wait()
        self._pre_work_loop()

    def _internal_health_check(self):
        # check if pogo is topmost and start if necessary
        log.debug(
            "_internal_health_check: Calling _start_pogo routine to check if pogo is topmost")
        self._work_mutex.acquire()
        log.debug("_internal_health_check: worker lock acquired")
        log.debug("Checking if we need to restart pogo")
        # Restart pogo every now and then...
        if self._devicesettings.get("restart_pogo", 80) > 0:
            # log.debug("main: Current time - lastPogoRestart: %s" % str(curTime - lastPogoRestart))
            # if curTime - lastPogoRestart >= (args.restart_pogo * 60):
            self._location_count += 1
            if self._location_count > self._devicesettings.get("restart_pogo", 80):
                log.error(
                    "scanned " + str(self._devicesettings.get("restart_pogo", 80)) + " locations, restarting pogo")
                pogo_started = self._restart_pogo()
                self._location_count = 0
            else:
                pogo_started = self._start_pogo()
        else:
            pogo_started = self._start_pogo()
        self._work_mutex.release()
        log.debug("_internal_health_check: worker lock released")
        return pogo_started

    def _internal_cleanup(self):
        self._cleanup()
        self._communicator.cleanup_websocket()
        # self.stop_worker()
        self.loop.call_soon_threadsafe(self.loop.stop)

    def _main_work_thread(self):
        # TODO: signal websocketserver the removal
        try:
            self._internal_pre_work()
        except (InternalStopWorkerException, WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException):
            log.error(
                "Failed initializing worker %s, connection terminated exceptionally" % str(self._id))
            return

        while not self._stop_worker_event.isSet():
            while self._timer.get_switch() and self._route_manager_nighttime is None:
                time.sleep(1)
            # check if stop_worker_event is set again since sleep may have taken ages ;)
            if self._stop_worker_event.is_set():
                break

            try:
                # TODO: consider getting results of health checks and aborting the entire worker?
                self._internal_health_check()
                self._health_check()
            except (InternalStopWorkerException, WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException):
                log.error("Websocket connection to %s lost while running healthchecks, "
                          "connection terminated exceptionally" % str(self._id))
                break

            try:
                settings = self._internal_grab_next_location()
                if settings is None and self._timer.get_switch():
                    continue
            except (InternalStopWorkerException, WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException):
                log.warning("Worker of %s does not support mode that's to be run, "
                            "connection terminated exceptionally" % str(self._id))
                break

            try:
                self._pre_location_update()
            except (InternalStopWorkerException, WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException):
                log.warning("Worker of %s stopping because of stop signal in pre_location_update, "
                            "connection terminated exceptionally" % str(self._id))
                break

            self._add_task_to_loop(self._update_position_file())

            try:
                log.debug('main worker %s: LastLat: %s, LastLng: %s, CurLat: %s, CurLng: %s' %
                          (str(self._id), self.last_location.lat, self.last_location.lng,
                           self.current_location.lat, self.current_location.lng))
                time_snapshot, process_location = self._move_to_location()
            except (InternalStopWorkerException, WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException):
                log.warning("Worker %s failed moving to new location, stopping worker, "
                            "connection terminated exceptionally" % str(self._id))
                break

            if process_location:

                if self._applicationArgs.last_scanned:
                    log.info('main: Set new scannedlocation in Database')
                    # self.update_scanned_location(currentLocation.lat, currentLocation.lng, curTime)
                    self._add_task_to_loop(self.update_scanned_location(
                        self.current_location.lat, self.current_location.lng, time_snapshot)
                    )

                try:
                    self._post_move_location_routine(time_snapshot)
                except (InternalStopWorkerException, WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException):
                    log.warning(
                        "Worker %s failed running post_move_location_routine, stopping worker" % str(self._id))
                    break
                log.info("Worker %s finished iteration, continuing work" %
                         str(self._id))

        self._internal_cleanup()

    async def _update_position_file(self):
        log.debug("Updating .position file")
        with open(self._id + '.position', 'w') as outfile:
            outfile.write(str(self.current_location.lat) +
                          ", " + str(self.current_location.lng))

    async def update_scanned_location(self, latitude, longitude, timestamp):
        try:
            self._db_wrapper.set_scanned_location(
                str(latitude), str(longitude), str(timestamp))
        except Exception as e:
            log.error("Failed updating scanned location: %s" % str(e))
            return

    def _get_currently_valid_routemanager(self):
        valid_modes = self._valid_modes()
        switch_mode = self._timer.get_switch()
        if (switch_mode and self._route_manager_nighttime is not None
                and self._route_manager_nighttime.mode in valid_modes):
            return self._route_manager_nighttime
        elif switch_mode is True and self._route_manager_nighttime is None:
            return None
        elif not switch_mode and self._route_manager_daytime.mode in valid_modes:
            return self._route_manager_daytime
        else:
            # log.fatal("Raising internal worker exception")
            raise InternalStopWorkerException

    def _internal_grab_next_location(self):
        # TODO: consider adding runWarningThreadEvent.set()
        self.last_location = self.current_location
        self._last_known_state["last_location"] = self.last_location

        log.debug("Requesting next location from routemanager")
        # requesting a location is blocking (iv_mitm will wait for a prioQ item), we really need to clean
        # the workers up...
        routemanager = self._get_currently_valid_routemanager()
        if routemanager is None:
            return None
        else:
            self.current_location = routemanager.get_next_location()
            return routemanager.settings

    def _init_routine(self):
        if self._applicationArgs.initial_restart is False:
            self._turn_screen_on_and_start_pogo()
        else:
            if not self._start_pogo():
                while not self._restart_pogo():
                    log.warning("failed starting pogo")
                    # TODO: stop after X attempts

    def _turn_screen_on_and_start_pogo(self):
        if not self._communicator.isScreenOn():
            self._communicator.startApp("de.grennith.rgc.remotegpscontroller")
            log.warning("Turning screen on")
            self._communicator.turnScreenOn()
            time.sleep(self._devicesettings.get(
                "post_turn_screen_on_delay", 2))
        # check if pogo is running and start it if necessary
        log.warning("turnScreenOnAndStartPogo: (Re-)Starting Pogo")
        self._start_pogo()

    def _check_screen_on(self):
        if not self._communicator.isScreenOn():
            self._communicator.startApp("de.grennith.rgc.remotegpscontroller")
            log.warning("Turning screen on")
            self._communicator.turnScreenOn()
            time.sleep(self._devicesettings.get(
                "post_turn_screen_on_delay", 2))

    def _stop_pogo(self):
        attempts = 0
        stop_result = self._communicator.stopApp("com.nianticlabs.pokemongo")
        pogoTopmost = self._communicator.isPogoTopmost()
        while pogoTopmost:
            attempts += 1
            if attempts > 10:
                return False
            stop_result = self._communicator.stopApp(
                "com.nianticlabs.pokemongo")
            time.sleep(1)
            pogoTopmost = self._communicator.isPogoTopmost()
        return stop_result

    def _reboot(self):
        try:
            start_result = self._communicator.reboot()
        except WebsocketWorkerRemovedException:
            log.error(
                "Could not reboot due to client already having disconnected")
            start_result = False
        time.sleep(5)
        self.stop_worker()
        return start_result

    def _start_pogodroid(self):
        start_result = self._communicator.startApp("com.mad.pogodroid")
        time.sleep(5)
        return start_result

    def _stopPogoDroid(self):
        stopResult = self._communicator.stopApp("com.mad.pogodroid")
        return stopResult

    def _restart_pogo(self, clear_cache=True):
        successful_stop = self._stop_pogo()
        log.debug("restartPogo: stop pogo resulted in %s" %
                  str(successful_stop))
        if successful_stop:
            if clear_cache:
                self._communicator.clearAppCache("com.nianticlabs.pokemongo")
            time.sleep(1)
            return self._start_pogo()
        else:
            return False

    def _restartPogoDroid(self):
        successfulStop = self._stopPogoDroid()
        time.sleep(1)
        log.debug("restartPogoDroid: stop pogodriud resulted in %s" %
                  str(successfulStop))
        if successfulStop:
            return self._start_pogodroid()
        else:
            return False

    def _reopenRaidTab(self):
        log.debug("_reopenRaidTab: Taking screenshot...")
        log.info(
            "reopenRaidTab: Attempting to retrieve screenshot before checking raidtab")
        if not self._takeScreenshot():
            log.debug("_reopenRaidTab: Failed getting screenshot...")
            log.error(
                "reopenRaidTab: Failed retrieving screenshot before checking for closebutton")
            return
        log.debug("_reopenRaidTab: Checking close except nearby...")
        pathToPass = os.path.join(
            self._applicationArgs.temp_path, 'screenshot%s.png' % str(self._id))
        log.debug("Path: %s" % str(pathToPass))
        self._pogoWindowManager.checkCloseExceptNearbyButton(
            pathToPass, self._id, 'True')
        log.debug("_reopenRaidTab: Getting to raidscreen...")
        self._getToRaidscreen(3)
        time.sleep(1)

    def _takeScreenshot(self, delayAfter=0.0, delayBefore=0.0):
        log.debug("Taking screenshot...")
        time.sleep(delayBefore)
        compareToTime = time.time() - self._lastScreenshotTaken
        log.debug("Last screenshot taken: %s" % str(self._lastScreenshotTaken))

        if self._applicationArgs.use_media_projection:
            take_screenshot = self._communicator.getScreenshot(os.path.join(
                self._applicationArgs.temp_path, 'screenshot%s.png' % str(self._id)))
        else:
            take_screenshot = self._communicator.get_screenshot_single(os.path.join(
                self._applicationArgs.temp_path, 'screenshot%s.png' % str(self._id)))

        if self._lastScreenshotTaken and compareToTime < 0.5:
            log.debug(
                "takeScreenshot: screenshot taken recently, returning immediately")
            log.debug("Screenshot taken recently, skipping")
            return True
        # TODO: screenshot.png needs identifier in name
        elif not take_screenshot:
            log.error("takeScreenshot: Failed retrieving screenshot")
            log.debug("Failed retrieving screenshot")
            return False
        else:
            log.debug("Success retrieving screenshot")
            self._lastScreenshotTaken = time.time()
            time.sleep(delayAfter)
            return True

    def _checkPogoFreeze(self):
        log.debug("Checking if pogo froze")
        if not self._takeScreenshot():
            log.debug("_checkPogoFreeze: failed retrieving screenshot")
            return
        from utils.image_utils import getImageHash
        screenHash = getImageHash(os.path.join(
            self._applicationArgs.temp_path, 'screenshot%s.png' % str(self._id)))
        log.debug("checkPogoFreeze: Old Hash: " + str(self._lastScreenHash))
        log.debug("checkPogoFreeze: New Hash: " + str(screenHash))
        if hamming_dist(str(self._lastScreenHash), str(screenHash)) < 4 and str(self._lastScreenHash) != '0':
            log.debug(
                "checkPogoFreeze: New und old Screenshoot are the same - no processing")
            self._lastScreenHashCount += 1
            log.debug("checkPogoFreeze: Same Screen Count: " +
                      str(self._lastScreenHashCount))
            if self._lastScreenHashCount >= 100:
                self._lastScreenHashCount = 0
                self._restart_pogo()
        else:
            self._lastScreenHash = screenHash
            self._lastScreenHashCount = 0

            log.debug("_checkPogoFreeze: done")

    def _check_pogo_main_screen(self, maxAttempts, again=False):
        log.debug("_check_pogo_main_screen: Trying to get to the Mainscreen with %s max attempts..." % str(
            maxAttempts))
        pogoTopmost = self._communicator.isPogoTopmost()
        if not pogoTopmost:
            return False

        self._checkPogoFreeze()
        if not self._takeScreenshot(delayBefore=self._applicationArgs.post_screenshot_delay):
            if again:
                log.error(
                    "_check_pogo_main_screen: failed getting a screenshot again")
                return False
            log.debug("_check_pogo_main_screen: Got screenshot, checking GPS")
        attempts = 0

        if os.path.isdir(os.path.join(self._applicationArgs.temp_path, 'screenshot%s.png' % str(self._id))):
            log.error(
                "_check_pogo_main_screen: screenshot.png is not a file/corrupted")
            return False

        while self._pogoWindowManager.isGpsSignalLost(os.path.join(self._applicationArgs.temp_path, 'screenshot%s.png' % str(self._id)), self._id):
            log.debug("_check_pogo_main_screen: GPS signal lost")
            time.sleep(1)
            self._takeScreenshot()
            log.warning("_check_pogo_main_screen: GPS signal error")
            self._redErrorCount += 1
            if self._redErrorCount > 3:
                log.error(
                    "_check_pogo_main_screen: Red error multiple times in a row, restarting")
                self._redErrorCount = 0
                self._restart_pogo()
                return False
        self._redErrorCount = 0
        log.info("_check_pogo_main_screen: checking mainscreen")
        while not self._pogoWindowManager.checkpogomainscreen(os.path.join(self._applicationArgs.temp_path, 'screenshot%s.png' % str(self._id)), self._id):
            log.error("_check_pogo_main_screen: not on Mainscreen...")
            if attempts > maxAttempts:
                # could not reach raidtab in given maxAttempts
                log.error("_check_pogo_main_screen: Could not get to Mainscreen within %s attempts" % str(
                    maxAttempts))
                return False
            self._checkPogoFreeze()
            # not using continue since we need to get a screen before the next round...
            found = self._pogoWindowManager.lookForButton(os.path.join(
                self._applicationArgs.temp_path, 'screenshot%s.png' % str(self._id)), 2.20, 3.01)
            if found:
                log.info("_check_pogo_main_screen: Found button (small)")

            if not found and self._pogoWindowManager.checkCloseExceptNearbyButton(
                    os.path.join(self._applicationArgs.temp_path, 'screenshot%s.png' % str(self._id)), self._id, closeraid=True):
                log.info(
                    "_check_pogo_main_screen: Found (X) button (except nearby)")
                found = True

            if not found and self._pogoWindowManager.lookForButton(os.path.join(self._applicationArgs.temp_path, 'screenshot%s.png' % str(self._id)), 1.05,
                                                                   2.20):
                log.info("_check_pogo_main_screen: Found button (big)")
                found = True

            log.info(
                "_check_pogo_main_screen: Previous checks found popups: %s" % str(found))

            attempts += 1
        log.info("_check_pogo_main_screen: done")
        return True

    def _checkPogoButton(self):
        log.debug("checkPogoButton: Trying to find buttons")
        pogoTopmost = self._communicator.isPogoTopmost()
        if not pogoTopmost:
            return False

        self._checkPogoFreeze()
        if not self._takeScreenshot(delayBefore=self._applicationArgs.post_screenshot_delay):
            # TODO: again?
            # if again:
            #     log.error("checkPogoButton: failed getting a screenshot again")
            #     return False
            # TODO: throw?
            log.debug("checkPogoButton: Failed getting screenshot")
            return False

        if os.path.isdir(os.path.join(self._applicationArgs.temp_path, 'screenshot%s.png' % str(self._id))):
            log.error("checkPogoButton: screenshot.png is not a file/corrupted")
            return False

        log.info("checkPogoButton: checking for buttons")
        found = self._pogoWindowManager.lookForButton(os.path.join(
            self._applicationArgs.temp_path, 'screenshot%s.png' % str(self._id)), 2.20, 3.01)
        if found:
            log.info("checkPogoButton: Found button (small)")
            log.info("checkPogoButton: done")
            return True
        log.info("checkPogoButton: done")
        return False

    def _checkPogoClose(self):
        log.debug("checkPogoClose: Trying to find closeX")
        pogoTopmost = self._communicator.isPogoTopmost()
        if not pogoTopmost:
            return False

        self._checkPogoFreeze()
        if not self._takeScreenshot(delayBefore=self._applicationArgs.post_screenshot_delay):
            # TODO: go again?
            # if again:
            #     log.error("checkPogoClose: failed getting a screenshot again")
            #     return False
            # TODO: consider throwing?
            log.debug("checkPogoClose: Could not get screenshot")
            return False

        if os.path.isdir(os.path.join(self._applicationArgs.temp_path, 'screenshot%s.png' % str(self._id))):
            log.error("checkPogoClose: screenshot.png is not a file/corrupted")
            return False

        log.info("checkPogoClose: checking for CloseX")
        found = self._pogoWindowManager.checkCloseExceptNearbyButton(
            os.path.join(self._applicationArgs.temp_path, 'screenshot%s.png' % str(self._id)), self._id)
        if found:
            log.info("checkPogoClose: Found (X) button (except nearby)")
            log.info("checkPogoClose: done")
            return True
        log.info("checkPogoClose: done")
        return False

    def _getToRaidscreen(self, maxAttempts, again=False):
        # check for any popups (including post login OK)
        log.debug("getToRaidscreen: Trying to get to the raidscreen with %s max attempts..." % str(
            maxAttempts))
        pogoTopmost = self._communicator.isPogoTopmost()
        if not pogoTopmost:
            return False

        self._checkPogoFreeze()
        if not self._takeScreenshot(delayBefore=self._applicationArgs.post_screenshot_delay):
            if again:
                log.error("getToRaidscreen: failed getting a screenshot again")
                return False
            self._getToRaidscreen(maxAttempts, True)
            log.debug("getToRaidscreen: Got screenshot, checking GPS")
        attempts = 0

        if os.path.isdir(os.path.join(self._applicationArgs.temp_path, 'screenshot%s.png' % str(self._id))):
            log.error("getToRaidscreen: screenshot.png is not a file/corrupted")
            return False

        # TODO: replace self._id with device ID
        while self._pogoWindowManager.isGpsSignalLost(os.path.join(self._applicationArgs.temp_path, 'screenshot%s.png' % str(self._id)), self._id):
            log.debug("getToRaidscreen: GPS signal lost")
            time.sleep(1)
            self._takeScreenshot()
            log.warning("getToRaidscreen: GPS signal error")
            self._redErrorCount += 1
            if self._redErrorCount > 3:
                log.error(
                    "getToRaidscreen: Red error multiple times in a row, restarting")
                self._redErrorCount = 0
                self._restart_pogo()
                return False
        self._redErrorCount = 0
        log.debug("getToRaidscreen: checking raidscreen")
        while not self._pogoWindowManager.checkRaidscreen(os.path.join(self._applicationArgs.temp_path, 'screenshot%s.png' % str(self._id)), self._id):
            log.debug("getToRaidscreen: not on raidscreen...")
            if attempts > maxAttempts:
                # could not reach raidtab in given maxAttempts
                log.error("getToRaidscreen: Could not get to raidtab within %s attempts" % str(
                    maxAttempts))
                return False
            self._checkPogoFreeze()
            # not using continue since we need to get a screen before the next round...
            found = self._pogoWindowManager.lookForButton(os.path.join(
                self._applicationArgs.temp_path, 'screenshot%s.png' % str(self._id)), 2.20, 3.01)
            if found:
                log.info("getToRaidscreen: Found button (small)")

            if not found and self._pogoWindowManager.checkCloseExceptNearbyButton(
                    os.path.join(self._applicationArgs.temp_path, 'screenshot%s.png' % str(self._id)), self._id):
                log.info("getToRaidscreen: Found (X) button (except nearby)")
                found = True

            if not found and self._pogoWindowManager.lookForButton(os.path.join(self._applicationArgs.temp_path, 'screenshot%s.png' % str(self._id)), 1.05,
                                                                   2.20):
                log.info("getToRaidscreen: Found button (big)")
                found = True

            log.info("getToRaidscreen: Previous checks found popups: %s" %
                     str(found))
            if not found:
                log.info(
                    "getToRaidscreen: Previous checks found nothing. Checking nearby open")
                if self._pogoWindowManager.checkNearby(os.path.join(self._applicationArgs.temp_path, 'screenshot%s.png' % str(self._id)), self._id):
                    return self._takeScreenshot(delayBefore=self._applicationArgs.post_screenshot_delay)

            if not self._takeScreenshot(delayBefore=self._applicationArgs.post_screenshot_delay):
                return False

            attempts += 1
        log.debug("getToRaidscreen: done")
        return True

    def _open_gym(self, delayadd):
        log.debug('{_open_gym} called')
        time.sleep(1)
        x, y = self._resocalc.get_gym_click_coords(
            self)[0], self._resocalc.get_gym_click_coords(self)[1]
        self._communicator.click(int(x), int(y))
        time.sleep(1 + int(delayadd))
        log.debug('{_open_gym} called')
        return

    def _spin_wheel(self, delayadd):
        log.debug('{_spin_wheel} called')
        x1, x2, y = self._resocalc.get_gym_spin_coords(self)[0], self._resocalc.get_gym_spin_coords(self)[
            1], self._resocalc.get_gym_spin_coords(self)[2]
        self._communicator.swipe(int(x1), int(y), int(x2), int(y))
        return

    def _close_gym(self, delayadd):
        log.debug('{_close_gym} called')
        x, y = self._resocalc.get_close_main_button_coords(
            self)[0], self._resocalc.get_close_main_button_coords(self)[1]
        self._communicator.click(int(x), int(y))
        time.sleep(1 + int(delayadd))
        log.debug('{_close_gym} called')

    def _turn_map(self, delayadd):
        log.debug('{_turn_map} called')
        x1, x2, y = self._resocalc.get_gym_spin_coords(self)[0], self._resocalc.get_gym_spin_coords(self)[
            1], self._resocalc.get_gym_spin_coords(self)[2]
        self._communicator.swipe(int(x1), int(y), int(x2), int(y))
        time.sleep(int(delayadd))
        log.debug('{_turn_map} called')
        return

    def _clear_quests(self, delayadd):
        log.debug('{_clear_quests} called')
        time.sleep(4 + int(delayadd))
        x, y = self._resocalc.get_coords_quest_menu(
            self)[0], self._resocalc.get_coords_quest_menu(self)[1]
        self._communicator.click(int(x), int(y))
        time.sleep(2 + int(delayadd))
        x, y = self._resocalc.get_delete_quest_coords(
            self)[0], self._resocalc.get_delete_quest_coords(self)[1]
        self._communicator.click(int(x), int(y))
        time.sleep(1 + int(delayadd))
        x, y = self._resocalc.get_confirm_delete_quest_coords(
            self)[0], self._resocalc.get_confirm_delete_quest_coords(self)[1]
        self._communicator.click(int(x), int(y))
        time.sleep(.5 + int(delayadd))
        x, y = self._resocalc.get_close_main_button_coords(
            self)[0], self._resocalc.get_close_main_button_coords(self)[1]
        self._communicator.click(int(x), int(y))
        log.debug('{_clear_quests} finished')
        return

    def _get_screen_size(self):
        screen = self._communicator.getscreensize().split(' ')
        self._screen_x = screen[0]
        self._screen_y = screen[1]
        log.debug('Get Screensize of %s: X: %s, Y: %s' %
                  (str(self._id), str(self._screen_x), str(self._screen_y)))
        self._resocalc.get_x_y_ratio(self, self._screen_x, self._screen_y)
