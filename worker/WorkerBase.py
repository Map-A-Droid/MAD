import asyncio
import collections
import functools
import os
import time
import math

from abc import ABC, abstractmethod
from utils.logging import logger
from threading import Event, Thread, current_thread, Lock
from utils.routeutil import check_walker_value_type, check_max_walkers_reached
from utils.hamming import hamming_distance as hamming_dist
from utils.madGlobals import WebsocketWorkerRemovedException, InternalStopWorkerException, \
    WebsocketWorkerTimeoutException
from utils.resolution import Resocalculator
from websocket.communicator import Communicator

Location = collections.namedtuple('Location', ['lat', 'lng'])


class WorkerBase(ABC):
    def __init__(self, args, id, last_known_state, websocket_handler,
                 walker_routemanager, devicesettings, db_wrapper, pogoWindowManager, NoOcr=True,
                 walker=None):
        # self.thread_pool = ThreadPool(processes=2)
        self._walker_routemanager = walker_routemanager
        self._route_manager_last_time = None
        self._websocket_handler = websocket_handler
        self._communicator = Communicator(websocket_handler, id, self, args.websocket_command_timeout)
        self._id = id
        self._applicationArgs = args
        self._last_known_state = last_known_state
        self._work_mutex = Lock()
        self.loop = None
        self.loop_started = Event()
        self.loop_tid = None
        self._async_io_looper_thread = None
        self._location_count = 0
        self._init = self._walker_routemanager.init
        self._walker = walker
        self._walkerstart = None

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
        self._lastStart = ""
        self._geofix_sleeptime = 0
        self._pogoWindowManager = pogoWindowManager

        self.current_location = Location(0.0, 0.0)
        self.last_location = self._devicesettings.get("last_location", None)
        if self.last_location is None:
            self.last_location = Location(0.0, 0.0)
        self.last_processed_location = Location(0.0, 0.0)

    def get_communicator(self):
        return self._communicator

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
            return f()  # We can call directly if we're not going between threads.
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
        logger.info("Worker {} stopping gracefully", str(self._id))
        # async_result.get()
        return self._last_known_state

    def stop_worker(self):
        self._stop_worker_event.set()
        logger.warning("Worker {} stop called", str(self._id))

    def _internal_pre_work(self):
        current_thread().name = self._id

        self._work_mutex.acquire()
        try:
            self._turn_screen_on_and_start_pogo()
        except WebsocketWorkerRemovedException:
            logger.error("Timeout during init of worker {}", str(self._id))
            # no cleanup required here? TODO: signal websocket server somehow
            self._stop_worker_event.set()
            return

        # register worker  in routemanager
        logger.info("Try to register {} in Routemanager {}", str(self._id), str(self._walker_routemanager.name))
        self._walker_routemanager.register_worker(self._id)

        self._work_mutex.release()

        self._async_io_looper_thread = Thread(name=str(self._id) + '_asyncio_' + self._id,
                                              target=self._start_asyncio_loop)
        self._async_io_looper_thread.daemon = False
        self._async_io_looper_thread.start()

        self.loop_started.wait()
        self._pre_work_loop()

    def _internal_health_check(self):
        # check if pogo is topmost and start if necessary
        logger.debug("_internal_health_check: Calling _start_pogo routine to check if pogo is topmost")
        self._work_mutex.acquire()
        logger.debug("_internal_health_check: worker lock acquired")
        logger.debug("Checking if we need to restart pogo")
        # Restart pogo every now and then...
        if self._devicesettings.get("restart_pogo", 80) > 0:
            # logger.debug("main: Current time - lastPogoRestart: {}", str(curTime - lastPogoRestart))
            # if curTime - lastPogoRestart >= (args.restart_pogo * 60):
            if self._location_count > self._devicesettings.get("restart_pogo", 80):
                logger.error(
                    "scanned " + str(self._devicesettings.get("restart_pogo", 80)) + " locations, restarting pogo")
                pogo_started = self._restart_pogo()
                self._location_count = 0
            else:
                pogo_started = self._start_pogo()
        else:
            pogo_started = self._start_pogo()
        self._work_mutex.release()
        logger.debug("_internal_health_check: worker lock released")
        return pogo_started

    def _internal_cleanup(self):
        # set the event just to make sure - in case of exceptions for example
        self._stop_worker_event.set()
        logger.info("Internal cleanup of {} started", str(self._id))
        self._cleanup()
        logger.info("Internal cleanup of {} signalling end to websocketserver", str(self._id))
        self._walker_routemanager.unregister_worker(self._id)

        logger.info("Stopping Route")
        # self.stop_worker()
        if self._async_io_looper_thread is not None:
            logger.info("Stopping worker's asyncio loop")
            self.loop.call_soon_threadsafe(self.loop.stop)
            self._async_io_looper_thread.join()

        self._communicator.cleanup_websocket()
        logger.info("Internal cleanup of {} finished", str(self._id))

    def _main_work_thread(self):
        # TODO: signal websocketserver the removal
        try:
            self._internal_pre_work()
        except (InternalStopWorkerException, WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException):
            logger.error("Failed initializing worker {}, connection terminated exceptionally", str(self._id))
            self._internal_cleanup()
            return

        if not check_max_walkers_reached(self._walker, self._walker_routemanager):
            logger.warning('Max. Walkers in Area {} - closing connections', str(self._walker_routemanager.name))
            self._devicesettings['finished'] = True
            self._internal_cleanup()
            return

        while not self._stop_worker_event.isSet():
            try:
                # TODO: consider getting results of health checks and aborting the entire worker?
                walkercheck = self.check_walker()
                if not walkercheck:
                    self._devicesettings['finished'] = True
                    break
            except (InternalStopWorkerException, WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException):
                logger.warning("Worker {} killed by walker settings", str(self._id))
                break

            try:
                # TODO: consider getting results of health checks and aborting the entire worker?
                self._internal_health_check()
                self._health_check()
            except (InternalStopWorkerException, WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException):
                logger.error("Websocket connection to {} lost while running healthchecks, connection terminated exceptionally", str(self._id))
                break

            try:
                settings = self._internal_grab_next_location()
                if settings is None:
                    continue
            except (InternalStopWorkerException, WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException):
                logger.warning("Worker of {} does not support mode that's to be run, connection terminated exceptionally", str(self._id))
                break

            try:
                logger.debug('Checking if new location is valid')
                valid = self._check_location_is_valid()
                if not valid:
                    break
            except (InternalStopWorkerException, WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException):
                logger.warning("Worker {} get non valid coords!", str(self._id))
                break

            try:
                self._pre_location_update()
            except (InternalStopWorkerException, WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException):
                logger.warning("Worker of {} stopping because of stop signal in pre_location_update, connection terminated exceptionally", str(self._id))
                break

            try:
                logger.debug('main worker {}: LastLat: {}, LastLng: {}, CurLat: {}, CurLng: {}',
                             str(self._id), self._devicesettings["last_location"].lat,
                             self._devicesettings["last_location"].lng, self.current_location.lat,
                             self.current_location.lng)
                time_snapshot, process_location = self._move_to_location()
            except (InternalStopWorkerException, WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException):
                logger.warning("Worker {} failed moving to new location, stopping worker, connection terminated exceptionally", str(self._id))
                break

            if process_location:
                self._add_task_to_loop(self._update_position_file())
                self._location_count += 1
                if self._applicationArgs.last_scanned:
                    logger.debug("Seting new 'scannedlocation' in Database")
                    # self.update_scanned_location(currentLocation.lat, currentLocation.lng, curTime)
                    self._add_task_to_loop(self.update_scanned_location(
                        self.current_location.lat, self.current_location.lng, time_snapshot)
                    )

                try:
                    self._post_move_location_routine(time_snapshot)
                except (InternalStopWorkerException, WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException):
                    logger.warning("Worker {} failed running post_move_location_routine, stopping worker", str(self._id))
                    break
                logger.info("Worker {} finished iteration, continuing work", str(self._id))

        self._internal_cleanup()

    async def _update_position_file(self):
        logger.debug("Updating .position file")
        if self.current_location is not None:
            with open(os.path.join(self._applicationArgs.file_path, self._id + '.position'), 'w') as outfile:
                outfile.write(str(self.current_location.lat) + ", " + str(self.current_location.lng))

    async def update_scanned_location(self, latitude, longitude, timestamp):
        try:
            self._db_wrapper.set_scanned_location(str(latitude), str(longitude), str(timestamp))
        except Exception as e:
            logger.error("Failed updating scanned location: {}", str(e))
            return

    def check_walker(self):
        mode = self._walker['walkertype']
        if mode == "countdown":
            logger.info("Checking walker mode 'countdown'")
            countdown = self._walker['walkervalue']
            if not countdown:
                logger.error("No Value for Mode - check your settings! Killing worker")
                return False
            if self._walkerstart is None:
                self._walkerstart = math.floor(time.time())
            else:
                if math.floor(time.time()) >= int(self._walkerstart) + int(countdown):
                    return False
            return True
        elif mode == "timer":
            logger.debug("Checking walker mode 'timer'")
            exittime = self._walker['walkervalue']
            if not exittime or ':' not in exittime:
                logger.error("No or wrong Value for Mode - check your settings! Killing worker")
                return False
            return check_walker_value_type(exittime)
        elif mode == "round":
            logger.debug("Checking walker mode 'round'")
            rounds = self._walker['walkervalue']
            if len(rounds) == 0:
                logger.error("No Value for Mode - check your settings! Killing worker")
                return False
            processed_rounds = self._walker_routemanager.get_rounds(self._id)
            if int(processed_rounds) >= int(rounds):
                return False
            return True
        elif mode == "period":
            logger.debug("Checking walker mode 'period'")
            period = self._walker['walkervalue']
            if len(period) == 0:
                logger.error("No Value for Mode - check your settings! Killing worker")
                return False
            return check_walker_value_type(period)
        elif mode == "coords":
            exittime = self._walker['walkervalue']
            if len(exittime) > 0:
                return check_walker_value_type(exittime)
            return True
        elif mode == "idle":
            logger.debug("Checking walker mode 'idle'")
            if len(self._walker['walkervalue']) == 0:
                logger.error("Wrong Value for mode - check your settings! Killing worker")
                return False
            sleeptime = self._walker['walkervalue']
            logger.info('{} going to sleep', str(self._id))
            killpogo = False
            if check_walker_value_type(sleeptime):
                self._stop_pogo()
                killpogo = True
            while not self._stop_worker_event.isSet() and check_walker_value_type(sleeptime):
                time.sleep(1)
            logger.info('{} just woke up', str(self._id))
            if killpogo:
                self._start_pogo()
            return False
        else:
            logger.error("Unknown walker mode! Killing worker")
            return False
        return True

    def set_geofix_sleeptime(self, sleeptime):
        self._geofix_sleeptime = sleeptime
        return True

    def _internal_grab_next_location(self):
        # TODO: consider adding runWarningThreadEvent.set()
        self._last_known_state["last_location"] = self.last_location

        logger.debug("Requesting next location from routemanager")
        # requesting a location is blocking (iv_mitm will wait for a prioQ item), we really need to clean
        # the workers up...
        if int(self._geofix_sleeptime) > 0:
            logger.info('Getting a geofix position from MADMin - sleeping for {} seconds', str(self._geofix_sleeptime))
            time.sleep(int(self._geofix_sleeptime))
            self._geofix_sleeptime = 0
        routemanager = self._walker_routemanager
        self.current_location = routemanager.get_next_location()
        return routemanager.settings

    def _init_routine(self):
        if self._applicationArgs.initial_restart is False:
            self._turn_screen_on_and_start_pogo()
        else:
            if not self._start_pogo():
                while not self._restart_pogo():
                    logger.warning("failed starting pogo")
                    # TODO: stop after X attempts

    def _check_location_is_valid(self):
        if self.current_location is None:
            # there are no more coords - so worker is finished successfully
            self._devicesettings['finished'] = True
            return None
        elif self.current_location is not None:
            logger.debug('Coords are valid')
            return True

    def _turn_screen_on_and_start_pogo(self):
        if not self._communicator.isScreenOn():
            self._communicator.startApp("de.grennith.rgc.remotegpscontroller")
            logger.warning("Turning screen on")
            self._communicator.turnScreenOn()
            time.sleep(self._devicesettings.get("post_turn_screen_on_delay", 2))
        # check if pogo is running and start it if necessary
        logger.info("turnScreenOnAndStartPogo: (Re-)Starting Pogo")
        self._start_pogo()

    def _check_screen_on(self):
        if not self._communicator.isScreenOn():
            self._communicator.startApp("de.grennith.rgc.remotegpscontroller")
            logger.warning("Turning screen on")
            self._communicator.turnScreenOn()
            time.sleep(self._devicesettings.get("post_turn_screen_on_delay", 2))

    def _stop_pogo(self):
        attempts = 0
        stop_result = self._communicator.stopApp("com.nianticlabs.pokemongo")
        pogoTopmost = self._communicator.isPogoTopmost()
        while pogoTopmost:
            attempts += 1
            if attempts > 10:
                return False
            stop_result = self._communicator.stopApp("com.nianticlabs.pokemongo")
            time.sleep(1)
            pogoTopmost = self._communicator.isPogoTopmost()
        return stop_result

    def _reboot(self):
        try:
            start_result = self._communicator.reboot()
        except WebsocketWorkerRemovedException:
            logger.error("Could not reboot due to client already having disconnected")
            start_result = False
        time.sleep(5)
        self._db_wrapper.save_last_reboot(self._id)
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
        self._db_wrapper.save_last_restart(self._id)
        logger.debug("restartPogo: stop pogo resulted in {}", str(successful_stop))
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
        logger.debug("restartPogoDroid: stop pogodriud resulted in {}", str(successfulStop))
        if successfulStop:
            return self._start_pogodroid()
        else:
            return False

    def _reopenRaidTab(self):
        logger.debug("_reopenRaidTab: Taking screenshot...")
        logger.info("reopenRaidTab: Attempting to retrieve screenshot before checking raidtab")
        if not self._takeScreenshot():
            logger.debug("_reopenRaidTab: Failed getting screenshot...")
            logger.error("reopenRaidTab: Failed retrieving screenshot before checking for closebutton")
            return
        logger.debug("_reopenRaidTab: Checking close except nearby...")
        pathToPass = os.path.join(self._applicationArgs.temp_path, 'screenshot%s.png' % str(self._id))
        logger.debug("Path: {}", str(pathToPass))
        self._pogoWindowManager.checkCloseExceptNearbyButton(pathToPass, self._id, self._communicator, 'True')
        logger.debug("_reopenRaidTab: Getting to raidscreen...")
        self._getToRaidscreen(3)
        time.sleep(1)

    def _takeScreenshot(self, delayAfter=0.0, delayBefore=0.0):
        logger.debug("Taking screenshot...")
        time.sleep(delayBefore)
        compareToTime = time.time() - self._lastScreenshotTaken
        logger.debug("Last screenshot taken: {}", str(self._lastScreenshotTaken))

        if self._applicationArgs.use_media_projection:
            take_screenshot = self._communicator.getScreenshot(os.path.join(self._applicationArgs.temp_path,
                                                                            'screenshot%s.png' % str(self._id)))
        else:
            take_screenshot = self._communicator.get_screenshot_single(os.path.join(self._applicationArgs.temp_path,
                                                                                    'screenshot%s.png' % str(self._id)))

        if self._lastScreenshotTaken and compareToTime < 0.5:
            logger.debug("takeScreenshot: screenshot taken recently, returning immediately")
            logger.debug("Screenshot taken recently, skipping")
            return True
        # TODO: screenshot.png needs identifier in name
        elif not take_screenshot:
            logger.error("takeScreenshot: Failed retrieving screenshot")
            logger.debug("Failed retrieving screenshot")
            return False
        else:
            logger.debug("Success retrieving screenshot")
            self._lastScreenshotTaken = time.time()
            time.sleep(delayAfter)
            return True

    def _checkPogoFreeze(self):
        logger.debug("Checking if pogo froze")
        if not self._takeScreenshot():
            logger.debug("_checkPogoFreeze: failed retrieving screenshot")
            return
        from utils.image_utils import getImageHash
        screenHash = getImageHash(os.path.join(self._applicationArgs.temp_path, 'screenshot%s.png' % str(self._id)))
        logger.debug("checkPogoFreeze: Old Hash: {}", str(self._lastScreenHash))
        logger.debug("checkPogoFreeze: New Hash: {}", str(screenHash))
        if hamming_dist(str(self._lastScreenHash), str(screenHash)) < 4 and str(self._lastScreenHash) != '0':
            logger.debug("checkPogoFreeze: New und old Screenshoot are the same - no processing")
            self._lastScreenHashCount += 1
            logger.debug("checkPogoFreeze: Same Screen Count: " + str(self._lastScreenHashCount))
            if self._lastScreenHashCount >= 100:
                self._lastScreenHashCount = 0
                self._restart_pogo()
        else:
            self._lastScreenHash = screenHash
            self._lastScreenHashCount = 0

            logger.debug("_checkPogoFreeze: done")

    def _check_pogo_main_screen(self, maxAttempts, again=False):
        logger.debug("_check_pogo_main_screen: Trying to get to the Mainscreen with {} max attempts...", str(maxAttempts))
        pogoTopmost = self._communicator.isPogoTopmost()
        if not pogoTopmost:
            return False

        if not self._takeScreenshot(delayBefore=self._devicesettings.get("post_screenshot_delay", 1)):
            if again:
                logger.error("_check_pogo_main_screen: failed getting a screenshot again")
                return False
        attempts = 0

        if os.path.isdir(os.path.join(self._applicationArgs.temp_path, 'screenshot%s.png' % str(self._id))):
            logger.error("_check_pogo_main_screen: screenshot.png is not a file/corrupted")
            return False

        logger.info("_check_pogo_main_screen: checking mainscreen")
        buttoncheck = self._pogoWindowManager.lookForButton(os.path.join(self._applicationArgs.temp_path,
                                                            'screenshot%s.png' % str(self._id)),
                                                            2.20, 3.01, self._communicator)
        if buttoncheck:
            logger.info('Found button on screen')
            self._takeScreenshot(delayBefore=self._devicesettings.get("post_screenshot_delay", 1))
        while not self._pogoWindowManager.checkpogomainscreen(os.path.join(self._applicationArgs.temp_path,
                                                                           'screenshot%s.png' % str(self._id)),
                                                              self._id):
            logger.error("_check_pogo_main_screen: not on Mainscreen...")
            if attempts > maxAttempts:
                # could not reach raidtab in given maxAttempts
                logger.error("_check_pogo_main_screen: Could not get to Mainscreen within {} attempts", str(maxAttempts))
                return False

            # not using continue since we need to get a screen before the next round...
            found = self._pogoWindowManager.lookForButton(os.path.join(self._applicationArgs.temp_path,
                                                                       'screenshot%s.png' % str(self._id)),
                                                          2.20, 3.01, self._communicator)
            if found:
                logger.info("_check_pogo_main_screen: Found button (small)")

            if not found and self._pogoWindowManager.checkCloseExceptNearbyButton(
                    os.path.join(self._applicationArgs.temp_path, 'screenshot%s.png' % str(self._id)), self._id,
                    self._communicator, closeraid=True):
                logger.info("_check_pogo_main_screen: Found (X) button (except nearby)")
                found = True

            if not found and self._pogoWindowManager.lookForButton(os.path.join(self._applicationArgs.temp_path,
                                                                                'screenshot%s.png' % str(self._id)),
                                                                   1.05, 2.20, self._communicator):
                logger.info("_check_pogo_main_screen: Found button (big)")
                found = True

            logger.info("_check_pogo_main_screen: Previous checks found popups: {}", str(found))

            self._takeScreenshot(delayBefore=self._devicesettings.get("post_screenshot_delay", 1))

            attempts += 1
        logger.info("_check_pogo_main_screen: done")
        return True

    def _checkPogoButton(self):
        logger.debug("checkPogoButton: Trying to find buttons")
        pogoTopmost = self._communicator.isPogoTopmost()
        if not pogoTopmost:
            return False

        if not self._takeScreenshot(delayBefore=self._devicesettings.get("post_screenshot_delay", 1)):
            # TODO: again?
            # if again:
            #     logger.error("checkPogoButton: failed getting a screenshot again")
            #     return False
            # TODO: throw?
            logger.debug("checkPogoButton: Failed getting screenshot")
            return False
        attempts = 0

        if os.path.isdir(os.path.join(self._applicationArgs.temp_path, 'screenshot%s.png' % str(self._id))):
            logger.error("checkPogoButton: screenshot.png is not a file/corrupted")
            return False

        logger.info("checkPogoButton: checking for buttons")
        found = self._pogoWindowManager.lookForButton(os.path.join(self._applicationArgs.temp_path,
                                                                   'screenshot%s.png' % str(self._id)), 2.20, 3.01,
                                                      self._communicator)
        if found:
            time.sleep(1)
            logger.info("checkPogoButton: Found button (small)")
            logger.info("checkPogoButton: done")
            return True
        logger.info("checkPogoButton: done")
        return False

    def _checkPogoClose(self):
        logger.debug("checkPogoClose: Trying to find closeX")
        pogoTopmost = self._communicator.isPogoTopmost()
        if not pogoTopmost:
            return False

        if not self._takeScreenshot(delayBefore=self._devicesettings.get("post_screenshot_delay", 1)):
            # TODO: go again?
            # if again:
            #     logger.error("checkPogoClose: failed getting a screenshot again")
            #     return False
            # TODO: consider throwing?
            logger.debug("checkPogoClose: Could not get screenshot")
            return False
        attempts = 0

        if os.path.isdir(os.path.join(self._applicationArgs.temp_path, 'screenshot%s.png' % str(self._id))):
            logger.error("checkPogoClose: screenshot.png is not a file/corrupted")
            return False

        logger.info("checkPogoClose: checking for CloseX")
        found = self._pogoWindowManager.checkCloseExceptNearbyButton(
                            os.path.join(self._applicationArgs.temp_path,
                                         'screenshot%s.png' % str(self._id)), self._id, self._communicator)
        if found:
            time.sleep(1)
            logger.info("checkPogoClose: Found (X) button (except nearby)")
            logger.info("checkPogoClose: done")
            return True
        logger.info("checkPogoClose: done")
        return False

    def _getToRaidscreen(self, maxAttempts, again=False):
        # check for any popups (including post login OK)
        logger.debug("getToRaidscreen: Trying to get to the raidscreen with {} max attempts...", str(maxAttempts))
        pogoTopmost = self._communicator.isPogoTopmost()
        if not pogoTopmost:
            return False

        self._checkPogoFreeze()
        if not self._takeScreenshot(delayBefore=self._devicesettings.get("post_screenshot_delay", 1)):
            if again:
                logger.error("getToRaidscreen: failed getting a screenshot again")
                return False
            self._getToRaidscreen(maxAttempts, True)
            logger.debug("getToRaidscreen: Got screenshot, checking GPS")
        attempts = 0

        if os.path.isdir(os.path.join(self._applicationArgs.temp_path, 'screenshot%s.png' % str(self._id))):
            logger.error("getToRaidscreen: screenshot.png is not a file/corrupted")
            return False

        # TODO: replace self._id with device ID
        while self._pogoWindowManager.isGpsSignalLost(os.path.join(self._applicationArgs.temp_path,
                                                                   'screenshot%s.png' % str(self._id)), self._id):
            logger.debug("getToRaidscreen: GPS signal lost")
            time.sleep(1)
            self._takeScreenshot()
            logger.warning("getToRaidscreen: GPS signal error")
            self._redErrorCount += 1
            if self._redErrorCount > 3:
                logger.error("getToRaidscreen: Red error multiple times in a row, restarting")
                self._redErrorCount = 0
                self._restart_pogo()
                return False
        self._redErrorCount = 0
        logger.debug("getToRaidscreen: checking raidscreen")
        while not self._pogoWindowManager.checkRaidscreen(os.path.join(self._applicationArgs.temp_path,
                                                                       'screenshot%s.png' % str(self._id)), self._id,
                                                          self._communicator):
            logger.debug("getToRaidscreen: not on raidscreen...")
            if attempts > maxAttempts:
                # could not reach raidtab in given maxAttempts
                logger.error("getToRaidscreen: Could not get to raidtab within {} attempts", str(maxAttempts))
                return False
            self._checkPogoFreeze()
            # not using continue since we need to get a screen before the next round...
            found = self._pogoWindowManager.lookForButton(os.path.join(
                self._applicationArgs.temp_path, 'screenshot%s.png' % str(self._id)), 2.20, 3.01, self._communicator)
            if found:
                logger.info("getToRaidscreen: Found button (small)")

            if not found and self._pogoWindowManager.checkCloseExceptNearbyButton(
                    os.path.join(self._applicationArgs.temp_path, 'screenshot%s.png' % str(self._id)), self._id,
                    self._communicator):
                logger.info("getToRaidscreen: Found (X) button (except nearby)")
                found = True

            if not found and self._pogoWindowManager.lookForButton(os.path.join(
                    self._applicationArgs.temp_path, 'screenshot%s.png' % str(self._id)), 1.05, 2.20,
                    self._communicator):
                logger.info("getToRaidscreen: Found button (big)")
                found = True

            logger.info("getToRaidscreen: Previous checks found popups: {}", str(found))
            if not found:
                logger.info("getToRaidscreen: Previous checks found nothing. Checking nearby open")
                if self._pogoWindowManager.checkNearby(os.path.join(self._applicationArgs.temp_path,
                                                                    'screenshot%s.png' % str(self._id)), self._id,
                                                       self._communicator):
                    return self._takeScreenshot(delayBefore=self._devicesettings.get("post_screenshot_delay", 1))

            if not self._takeScreenshot(delayBefore=self._devicesettings.get("post_screenshot_delay", 1)):
                return False

            attempts += 1
        logger.debug("getToRaidscreen: done")
        return True

    def _get_screen_size(self):
        screen = self._communicator.getscreensize().split(' ')
        self._screen_x = screen[0]
        self._screen_y = screen[1]
        x_offset = self._devicesettings.get("screenshot_x_offset", 0)
        y_offset = self._devicesettings.get("screenshot_y_offset", 0)
        logger.debug('Get Screensize of {}: X: {}, Y: {}, X-Offset: {}, Y-Offset: {}', str(self._id), str(self._screen_x), str(self._screen_y), str(x_offset), str(y_offset))
        self._resocalc.get_x_y_ratio(self, self._screen_x, self._screen_y, x_offset, y_offset)
