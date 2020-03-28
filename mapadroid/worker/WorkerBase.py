import asyncio
import collections
import functools
import math
import os
import time
from abc import abstractmethod
from threading import Event, Lock, Thread, current_thread
from typing import Optional, Union

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.mitm_receiver.MitmMapper import MitmMapper
from mapadroid.ocr.pogoWindows import PogoWindows
from mapadroid.ocr.screenPath import WordToScreenMatching
from mapadroid.ocr.screen_type import ScreenType
from mapadroid.utils import MappingManager
from mapadroid.utils.collections import Location
from mapadroid.utils.hamming import hamming_distance
from mapadroid.utils.logging import logger
from mapadroid.utils.madGlobals import (
    InternalStopWorkerException,
    WebsocketWorkerRemovedException,
    WebsocketWorkerTimeoutException,
    ScreenshotType,
    WebsocketWorkerConnectionClosedException)
from mapadroid.utils.resolution import Resocalculator
from mapadroid.utils.routeutil import check_walker_value_type
from mapadroid.websocket.AbstractCommunicator import AbstractCommunicator
from mapadroid.worker.AbstractWorker import AbstractWorker


class WorkerBase(AbstractWorker):
    def __init__(self, args, dev_id, origin, last_known_state, communicator: AbstractCommunicator,
                 mapping_manager: MappingManager,
                 area_id: int, routemanager_name: str, db_wrapper: DbWrapper, pogoWindowManager: PogoWindows,
                 NoOcr: bool = True,
                 walker=None, event=None):
        AbstractWorker.__init__(self, origin=origin, communicator=communicator)
        self._mapping_manager: MappingManager = mapping_manager
        self._routemanager_name: str = routemanager_name
        self._area_id = area_id

        self._dev_id: int = dev_id
        self._event = event
        self._origin: str = origin
        self._applicationArgs = args
        self._last_known_state = last_known_state
        self._work_mutex = Lock()
        self.loop = None
        self.loop_started = Event()
        self.loop_tid = None
        self._async_io_looper_thread = None
        self._location_count = 0
        self._init: bool = self._mapping_manager.routemanager_get_init(self._routemanager_name)
        self._walker = walker

        self._lastScreenshotTaken = 0
        self._stop_worker_event = Event()
        self._db_wrapper = db_wrapper
        self._redErrorCount = 0
        self._lastScreenHash = None
        self._lastScreenHashCount = 0
        self._resocalc = Resocalculator
        self._screen_x = 0
        self._screen_y = 0
        self._lastStart = ""
        self._geofix_sleeptime = 0
        self._pogoWindowManager = pogoWindowManager
        self._waittime_without_delays = 0
        self._transporttype = 0
        self._not_injected_count: int = 0
        self._same_screen_count: int = 0
        self._last_screen_type: ScreenType = ScreenType.UNDEFINED
        self._loginerrorcounter: int = 0

        self.current_location = Location(0.0, 0.0)
        self.last_location = self.get_devicesettings_value("last_location", None)

        if self.last_location is None:
            self.last_location = Location(0.0, 0.0)

        if self.get_devicesettings_value('last_mode', None) is not None and \
                self.get_devicesettings_value('last_mode') in ("raids_mitm", "mon_mitm", "iv_mitm"):
            # Reset last_location - no useless waiting delays (otherwise stop mode)
            logger.info('{}: last Mode not pokestop - reset saved location', str(self._origin))
            self.last_location = Location(0.0, 0.0)

        self.set_devicesettings_value("last_mode",
                                      self._mapping_manager.routemanager_get_mode(self._routemanager_name))
        self.last_processed_location = Location(0.0, 0.0)
        self.workerstart = None
        self._WordToScreenMatching = WordToScreenMatching(self._communicator, self._pogoWindowManager,
                                                          self._origin,
                                                          self._resocalc, mapping_manager,
                                                          self._applicationArgs)

    def set_devicesettings_value(self, key: str, value):
        self._mapping_manager.set_devicesetting_value_of(self._origin, key, value)

    def get_devicesettings_value(self, key: str, default_value: object = None):
        logger.debug2("Fetching devicemappings of {}".format(self._origin))
        try:
            devicemappings: Optional[dict] = self._mapping_manager.get_devicemappings_of(self._origin)
        except (EOFError, FileNotFoundError) as e:
            logger.warning("Failed fetching devicemappings in worker {} with description: {}. Stopping worker"
                           .format(str(self._origin), str(e)))
            self._stop_worker_event.set()
            return None
        if devicemappings is None:
            return default_value
        return devicemappings.get("settings", {}).get(key, default_value)

    def get_communicator(self):
        return self._communicator

    def get_screenshot_path(self, fileaddon: bool = False) -> str:
        screenshot_ending: str = ".jpg"
        addon: str = ""
        if self.get_devicesettings_value("screenshot_type", "jpeg") == "png":
            screenshot_ending = ".png"

        if fileaddon:
            addon: str = "_" + str(time.time())

        screenshot_filename = "screenshot_{}{}{}".format(str(self._origin), str(addon), screenshot_ending)

        if fileaddon:
            logger.info("Creating debugscreen: {}".format(screenshot_filename))

        return os.path.join(
            self._applicationArgs.temp_path, screenshot_filename)

    def check_max_walkers_reached(self):
        walkermax = self._walker.get('walkermax', False)
        if walkermax is False or (type(walkermax) is str and len(walkermax) == 0):
            return True
        reg_workers = self._mapping_manager.routemanager_get_registered_workers(self._routemanager_name)
        if len(reg_workers) > int(walkermax):
            return False
        return True

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

    @abstractmethod
    def _worker_specific_setup_start(self):
        """
        Routine preparing the state to scan. E.g. starting specific apps or clearing certain files
        Returns:
        """

    @abstractmethod
    def _worker_specific_setup_stop(self):
        """
        Routine destructing the state to scan. E.g. stopping specific apps or clearing certain files
        Returns:
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
        t_main_work.daemon = True
        t_main_work.start()
        # do some other stuff in the main process
        while not self._stop_worker_event.isSet():
            time.sleep(1)

        while t_main_work.is_alive():
            time.sleep(1)
            t_main_work.join()
        logger.info("Worker {} stopped gracefully", str(self._origin))
        # async_result.get()
        return self._last_known_state

    def stop_worker(self):
        if self._stop_worker_event.set():
            logger.info('Worker {} already stopped - waiting for it', str(self._origin))
        else:
            self._stop_worker_event.set()
            logger.warning("Worker {} stop called", str(self._origin))

    def _internal_pre_work(self):
        current_thread().name = self._origin

        if self.get_devicesettings_value("startcoords_of_walker", None) is not None:
            startcoords = self.get_devicesettings_value("startcoords_of_walker").replace(' ', '') \
                .replace('_', '').split(',')
            logger.info('Setting startcoords or walker lat {} / lng {}'.format(str(startcoords[0]),
                                                                               str(startcoords[1])))
            self._communicator.set_location(Location(startcoords[0], startcoords[1]), 0)

        with self._work_mutex:
            try:
                self._turn_screen_on_and_start_pogo()
                self._get_screen_size()
                # register worker  in routemanager
                logger.info("Try to register {} in Routemanager {}", str(
                    self._origin), str(self._mapping_manager.routemanager_get_name(self._routemanager_name)))
                self._mapping_manager.register_worker_to_routemanager(self._routemanager_name, self._origin)
            except WebsocketWorkerRemovedException:
                logger.error("Timeout during init of worker {}", str(self._origin))
                # no cleanup required here? TODO: signal websocket server somehow
                self._stop_worker_event.set()
                return

        self._async_io_looper_thread = Thread(name=str(self._origin) + '_asyncio_' + self._origin,
                                              target=self._start_asyncio_loop)
        self._async_io_looper_thread.daemon = True
        self._async_io_looper_thread.start()

        self.loop_started.wait()
        self._pre_work_loop()

    def _internal_health_check(self):
        # check if pogo is topmost and start if necessary
        logger.debug(
            "_internal_health_check: Calling _start_pogo routine to check if pogo is topmost")
        pogo_started = False
        with self._work_mutex:
            logger.debug("_internal_health_check: worker lock acquired")
            logger.debug("Checking if we need to restart pogo")
            # Restart pogo every now and then...
            restart_pogo_setting = self.get_devicesettings_value("restart_pogo", 0)
            if restart_pogo_setting > 0:
                # logger.debug("main: Current time - lastPogoRestart: {}", str(curTime - lastPogoRestart))
                # if curTime - lastPogoRestart >= (args.restart_pogo * 60):
                if self._location_count > restart_pogo_setting:
                    logger.info(
                        "scanned {} locations, restarting game on {}", str(restart_pogo_setting),
                        str(self._origin))
                    pogo_started = self._restart_pogo()
                    self._location_count = 0
                else:
                    pogo_started = self._start_pogo()
            else:
                pogo_started = self._start_pogo()

        logger.debug("_internal_health_check: worker lock released")
        return pogo_started

    def _internal_cleanup(self):
        # set the event just to make sure - in case of exceptions for example
        self._stop_worker_event.set()
        try:
            self._mapping_manager.unregister_worker_from_routemanager(self._routemanager_name, self._origin)
        except ConnectionResetError as e:
            logger.warning("Failed unregistering from routemanager, routemanager may have stopped running already."
                           "Exception: {}", e)
        logger.info("Internal cleanup of {} started", str(self._origin))
        self._cleanup()
        logger.info(
            "Internal cleanup of {} signalling end to websocketserver", str(self._origin))

        if self._async_io_looper_thread is not None:
            logger.info("Stopping worker's asyncio loop")
            self.loop.call_soon_threadsafe(self.loop.stop)
            self._async_io_looper_thread.join()

        self._communicator.cleanup()

        logger.info("Internal cleanup of {} finished", str(self._origin))

    def _main_work_thread(self):
        # TODO: signal websocketserver the removal
        try:
            self._internal_pre_work()
        except (InternalStopWorkerException, WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException,
                WebsocketWorkerConnectionClosedException):
            logger.error(
                "Failed initializing worker {}, connection terminated exceptionally", str(self._origin))
            self._internal_cleanup()
            return

        if not self.check_max_walkers_reached():
            logger.warning('Max. Walkers in Area {} - closing connections',
                           str(self._mapping_manager.routemanager_get_name(self._routemanager_name)))
            self.set_devicesettings_value('finished', True)
            self._internal_cleanup()
            return

        while not self._stop_worker_event.isSet():
            try:
                # TODO: consider getting results of health checks and aborting the entire worker?
                walkercheck = self.check_walker()
                if not walkercheck:
                    self.set_devicesettings_value('finished', True)
                    break
            except (InternalStopWorkerException, WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException,
                    WebsocketWorkerConnectionClosedException):
                logger.warning(
                    "Worker {} killed by walker settings", str(self._origin))
                break

            try:
                # TODO: consider getting results of health checks and aborting the entire worker?
                self._internal_health_check()
                self._health_check()
            except (InternalStopWorkerException, WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException,
                    WebsocketWorkerConnectionClosedException):
                logger.error(
                    "Websocket connection to {} lost while running healthchecks, connection terminated "
                    "exceptionally",
                    str(self._origin))
                break

            try:
                settings = self._internal_grab_next_location()
                if settings is None:
                    continue
            except (InternalStopWorkerException, WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException,
                    WebsocketWorkerConnectionClosedException):
                logger.warning(
                    "Worker of {} does not support mode that's to be run, connection terminated exceptionally",
                    str(self._origin))
                break

            try:
                logger.debug('Checking if new location is valid')
                valid = self._check_location_is_valid()
                if not valid:
                    break
            except (InternalStopWorkerException, WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException,
                    WebsocketWorkerConnectionClosedException):
                logger.warning(
                    "Worker {} get non valid coords!", str(self._origin))
                break

            try:
                self._pre_location_update()
            except (InternalStopWorkerException, WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException,
                    WebsocketWorkerConnectionClosedException):
                logger.warning(
                    "Worker of {} stopping because of stop signal in pre_location_update, connection terminated "
                    "exceptionally",
                    str(self._origin))
                break

            try:
                logger.debug('main worker {}: LastLat: {}, LastLng: {}, CurLat: {}, CurLng: {}',
                             str(
                                 self._origin),
                             self.get_devicesettings_value("last_location", Location(0, 0)).lat,
                             self.get_devicesettings_value("last_location", Location(0, 0)).lng,
                             self.current_location.lat, self.current_location.lng)
                time_snapshot, process_location = self._move_to_location()
            except (InternalStopWorkerException, WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException,
                    WebsocketWorkerConnectionClosedException):
                logger.warning(
                    "Worker {} failed moving to new location, stopping worker, connection terminated exceptionally",
                    str(self._origin))
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
                except (InternalStopWorkerException, WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException,
                        WebsocketWorkerConnectionClosedException):
                    logger.warning(
                        "Worker {} failed running post_move_location_routine, stopping worker",
                        str(self._origin))
                    break
                logger.info(
                    "Worker {} finished iteration, continuing work", str(self._origin))

        self._internal_cleanup()

    async def _update_position_file(self):
        logger.debug("Updating .position file")
        if self.current_location is not None:
            with open(os.path.join(self._applicationArgs.file_path, self._origin + '.position'),
                      'w') as outfile:
                outfile.write(str(self.current_location.lat) +
                              ", " + str(self.current_location.lng))

    async def update_scanned_location(self, latitude, longitude, timestamp):
        try:
            self._db_wrapper.set_scanned_location(
                str(latitude), str(longitude), str(timestamp))
        except Exception as e:
            logger.error("Failed updating scanned location: {}", str(e))
            return

    def check_walker(self):
        mode = self._walker['walkertype']
        walkereventid = self._walker.get('eventid', None)
        if walkereventid is not None and walkereventid != self._event.get_current_event_id():
            logger.warning("A other Event has started - leaving now")
            return False
        if mode == "countdown":
            logger.info("Checking walker mode 'countdown'")
            countdown = self._walker['walkervalue']
            if not countdown:
                logger.error(
                    "No Value for Mode - check your settings! Killing worker")
                return False
            if self.workerstart is None:
                self.workerstart = math.floor(time.time())
            else:
                if math.floor(time.time()) >= int(self.workerstart) + int(countdown):
                    return False
            return True
        elif mode == "timer":
            logger.debug("Checking walker mode 'timer'")
            exittime = self._walker['walkervalue']
            if not exittime or ':' not in exittime:
                logger.error(
                    "No or wrong Value for Mode - check your settings! Killing worker")
                return False
            return check_walker_value_type(exittime)
        elif mode == "round":
            logger.debug("Checking walker mode 'round'")
            rounds = self._walker['walkervalue']
            if len(rounds) == 0:
                logger.error(
                    "No Value for Mode - check your settings! Killing worker")
                return False
            processed_rounds = self._mapping_manager.routemanager_get_rounds(self._routemanager_name,
                                                                             self._origin)
            if int(processed_rounds) >= int(rounds):
                return False
            return True
        elif mode == "period":
            logger.debug("Checking walker mode 'period'")
            period = self._walker['walkervalue']
            if len(period) == 0:
                logger.error(
                    "No Value for Mode - check your settings! Killing worker")
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
                logger.error(
                    "Wrong Value for mode - check your settings! Killing worker")
                return False
            sleeptime = self._walker['walkervalue']
            logger.info('{} going to sleep', str(self._origin))
            killpogo = False
            if check_walker_value_type(sleeptime):
                self._stop_pogo()
                killpogo = True
            while not self._stop_worker_event.isSet() and check_walker_value_type(sleeptime):
                time.sleep(1)
            logger.info('{} just woke up', str(self._origin))
            if killpogo:
                self._start_pogo()
            return False
        else:
            logger.error("Unknown walker mode! Killing worker")
            return False

    def set_geofix_sleeptime(self, sleeptime: int) -> bool:
        self._geofix_sleeptime = sleeptime
        return True

    def _internal_grab_next_location(self):
        # TODO: consider adding runWarningThreadEvent.set()
        self._last_known_state["last_location"] = self.last_location

        logger.debug("Requesting next location from routemanager")
        # requesting a location is blocking (iv_mitm will wait for a prioQ item), we really need to clean
        # the workers up...
        if int(self._geofix_sleeptime) > 0:
            logger.info('Getting a geofix position from MADMin - sleeping for {} seconds',
                        str(self._geofix_sleeptime))
            time.sleep(int(self._geofix_sleeptime))
            self._geofix_sleeptime = 0

        self._check_for_mad_job()

        self.current_location = self._mapping_manager.routemanager_get_next_location(self._routemanager_name,
                                                                                     self._origin)
        return self._mapping_manager.routemanager_get_settings(self._routemanager_name)

    def _check_for_mad_job(self):
        if self.get_devicesettings_value("job", False):
            logger.info("Worker {} get a job - waiting".format(str(self._origin)))
            while self.get_devicesettings_value("job", False) and not self._stop_worker_event.is_set():
                time.sleep(10)
            logger.info("Worker {} processed the job and go on ".format(str(self._origin)))

    def _check_location_is_valid(self):
        if self.current_location is None:
            # there are no more coords - so worker is finished successfully
            self.set_devicesettings_value('finished', True)
            return None
        elif self.current_location is not None:
            logger.debug('Coords are valid')
            return True

    def _turn_screen_on_and_start_pogo(self):
        if not self._communicator.is_screen_on():
            self._communicator.start_app("de.grennith.rgc.remotegpscontroller")
            logger.warning("Turning screen on")
            self._communicator.turn_screen_on()
            time.sleep(self.get_devicesettings_value("post_turn_screen_on_delay", 2))
        # check if pogo is running and start it if necessary
        logger.info("turnScreenOnAndStartPogo: (Re-)Starting Pogo")
        self._start_pogo()

    def _check_screen_on(self):
        if not self._communicator.is_screen_on():
            self._communicator.start_app("de.grennith.rgc.remotegpscontroller")
            logger.warning("Turning screen on")
            self._communicator.turn_screen_on()
            time.sleep(self.get_devicesettings_value("post_turn_screen_on_delay", 2))

    def _ensure_pogo_topmost(self):
        logger.info('Checking pogo screen...')

        while not self._stop_worker_event.is_set():
            screen_type: ScreenType = self._WordToScreenMatching.detect_screentype()
            if screen_type in [ScreenType.POGO, ScreenType.QUEST]:
                self._last_screen_type = screen_type
                logger.debug2("Found pogo or questlog to be open")
                break
            elif screen_type != ScreenType.ERROR and self._last_screen_type == screen_type:
                logger.info("Found screen multiple times in a row")
                if self._same_screen_count < 3:
                    self._same_screen_count += 1
                else:
                    logger.warning('Game froze - restarting device')
                    self._reboot()
                    break

            # now handle all screens that may not have been handled by detect_screentype since that only clicks around
            # so any clearing data whatsoever happens here (for now)
            if screen_type == ScreenType.UNDEFINED:
                logger.error("Undefined screentype!")
            if screen_type == ScreenType.BLACK:
                logger.info("Found Black Loading Screen - waiting ...")
                time.sleep(20)

            if screen_type in [ScreenType.GAMEDATA, ScreenType.CONSENT, ScreenType.CLOSE]:
                logger.warning('Error getting Gamedata or strange ggl message appears')
                self._loginerrorcounter += 1
                if self._loginerrorcounter < 2:
                    self._restart_pogo_safe()
            elif screen_type == ScreenType.DISABLED:
                # Screendetection is disabled
                break
            elif screen_type == ScreenType.UPDATE:
                logger.warning(
                    'Found update pogo screen - sleeping 5 minutes for another check of the screen')
                # update pogo - later with new rgc version
                time.sleep(300)
            elif screen_type in [ScreenType.ERROR, ScreenType.FAILURE]:
                logger.warning('Something wrong with screendetection or pogo failure screen')
                self._loginerrorcounter += 1
            elif screen_type == ScreenType.GPS:
                logger.warning("Detected GPS error 11 - rebooting device")
                self._reboot()
            elif screen_type == ScreenType.SN:
                logger.warning('Getting SN Screen - restart PoGo and later PD')
                self._restart_pogo_safe()
                break

            if self._loginerrorcounter > 1:
                logger.error('Could not login again - (clearing game data + restarting device')
                self._stop_pogo()
                self._communicator.clear_app_cache("com.nianticlabs.pokemongo")
                if self.get_devicesettings_value('clear_game_data', False):
                    logger.info('Clearing game data')
                    self._communicator.reset_app_data("com.nianticlabs.pokemongo")
                self._loginerrorcounter = 0
                self._reboot()
                break

            self._last_screen_type = screen_type
        logger.info('Checking pogo screen is finished')
        return True

    def _restart_pogo_safe(self):
        self._stop_pogo()
        time.sleep(1)
        if self._applicationArgs.enable_worker_specific_extra_start_stop_handling:
            self._worker_specific_setup_stop()
            time.sleep(1)
        self._communicator.magisk_off()
        time.sleep(1)
        self._communicator.magisk_on()
        time.sleep(1)
        self._communicator.start_app("com.nianticlabs.pokemongo")
        time.sleep(25)
        self._stop_pogo()
        time.sleep(1)
        if self._applicationArgs.enable_worker_specific_extra_start_stop_handling:
            self._worker_specific_setup_start()
            time.sleep(1)
        return self._communicator.start_app("com.nianticlabs.pokemongo")

    def _switch_user(self):
        logger.info('Switching User - please wait ...')
        self._stop_pogo()
        time.sleep(5)
        self._communicator.reset_app_data("com.nianticlabs.pokemongo")
        self._turn_screen_on_and_start_pogo()
        if not self._ensure_pogo_topmost():
            logger.error('Kill Worker...')
            self._stop_worker_event.set()
            return False
        logger.info('Switching finished ...')
        return True

    def trigger_check_research(self):
        if "pokestops" in self._valid_modes():
            logger.warning("Cannot check for research menu while pokestops mode")
            return
        reached_main_menu = self._check_pogo_main_screen(3, True)
        if reached_main_menu:
            self._check_quest()
            time.sleep(2)
        return

    def _check_quest(self) -> ScreenType:
        logger.info('Precheck Quest Menu')
        questcounter: int = 0
        questloop: int = 0
        firstround: bool = True
        x, y = self._resocalc.get_coords_quest_menu(self)[0], \
               self._resocalc.get_coords_quest_menu(self)[1]
        self._communicator.click(int(x), int(y))
        time.sleep(10)
        returncode: ScreenType = ScreenType.UNDEFINED
        if not self._takeScreenshot(delayBefore=self.get_devicesettings_value("post_screenshot_delay", 1),
                                    delayAfter=2):
            logger.error("_check_windows: Failed getting screenshot")
            return ScreenType.ERROR

        while not returncode == ScreenType.POGO and not self._stop_worker_event.isSet():
            returncode = self._WordToScreenMatching.checkQuest(self.get_screenshot_path())

            if returncode == ScreenType.QUEST:
                questcounter += 1
                if firstround:
                    logger.info('First round getting research menu')
                    x, y = self._resocalc.get_close_main_button_coords(self)[0], \
                           self._resocalc.get_close_main_button_coords(self)[1]
                    self._communicator.click(int(x), int(y))
                    time.sleep(1.5)
                    return ScreenType.POGO
                elif questcounter >= 2:
                    logger.info('Getting research menu two times in row')
                    x, y = self._resocalc.get_close_main_button_coords(self)[0], \
                           self._resocalc.get_close_main_button_coords(self)[1]
                    self._communicator.click(int(x), int(y))
                    time.sleep(1.5)
                    return ScreenType.POGO

            x, y = self._resocalc.get_close_main_button_coords(self)[0], \
                   self._resocalc.get_close_main_button_coords(self)[1]
            self._communicator.click(int(x), int(y))
            time.sleep(1.5)
            x, y = self._resocalc.get_coords_quest_menu(self)[0], \
                   self._resocalc.get_coords_quest_menu(self)[1]
            self._communicator.click(int(x), int(y))
            time.sleep(3)
            self._takeScreenshot(delayBefore=self.get_devicesettings_value("post_screenshot_delay", 1),
                                 delayAfter=2)
            if questloop > 5:
                logger.warning("Give up - maybe research screen is there...")
                return ScreenType.POGO
            questloop += 1
            firstround = False

        return ScreenType.POGO

    def _start_pogo(self) -> bool:
        """
        Routine to start pogo.
        Return the state as a boolean do indicate a successful start
        :return:
        """
        pogo_topmost = self._communicator.is_pogo_topmost()
        if pogo_topmost:
            return True

        if not self._communicator.is_screen_on():
            self._communicator.start_app("de.grennith.rgc.remotegpscontroller")
            logger.warning("Turning screen on")
            self._communicator.turn_screen_on()
            time.sleep(self.get_devicesettings_value("post_turn_screen_on_delay", 7))

        # Disable vibration
        # This only needs to be done once per boot
        # So, we'll just do it when pogo actually needs starting
        # self._communicator.passthrough("su -c chmod 444 /sys/devices/virtual/timed_output/vibrator/enable")

        cur_time = time.time()
        start_result = False
        while not pogo_topmost:
            start_result = self._communicator.start_app(
                "com.nianticlabs.pokemongo")
            time.sleep(1)
            pogo_topmost = self._communicator.is_pogo_topmost()

        if start_result:
            logger.success("startPogo: Started pogo successfully...")
            self._last_known_state["lastPogoRestart"] = cur_time

        self._wait_pogo_start_delay()
        return start_result

    def is_stopping(self) -> bool:
        return self._stop_worker_event.is_set()

    def _stop_pogo(self):
        attempts = 0
        stop_result = self._communicator.stop_app("com.nianticlabs.pokemongo")
        pogoTopmost = self._communicator.is_pogo_topmost()
        while pogoTopmost:
            attempts += 1
            if attempts > 10:
                return False
            stop_result = self._communicator.stop_app(
                "com.nianticlabs.pokemongo")
            time.sleep(1)
            pogoTopmost = self._communicator.is_pogo_topmost()
        return stop_result

    def _reboot(self, mitm_mapper: Optional[MitmMapper] = None):
        try:
            start_result = self._communicator.reboot()
        except WebsocketWorkerRemovedException:
            logger.error(
                "Could not reboot due to client already disconnected")
            start_result = False
        time.sleep(5)
        if mitm_mapper is not None:
            mitm_mapper.collect_location_stats(self._origin, self.current_location, 1, time.time(), 3, 0,
                                               self._mapping_manager.routemanager_get_mode(
                                                   self._routemanager_name),
                                               99)
        self._db_wrapper.save_last_reboot(self._dev_id)
        self._reboot_count = 0
        self._restart_count = 0
        self.stop_worker()
        return start_result

    def _restart_pogo(self, clear_cache=True, mitm_mapper: Optional[MitmMapper] = None):
        successful_stop = self._stop_pogo()
        self._db_wrapper.save_last_restart(self._dev_id)
        self._restart_count = 0
        logger.debug("restartPogo: stop game resulted in {}",
                     str(successful_stop))
        if successful_stop:
            if clear_cache:
                self._communicator.clear_app_cache("com.nianticlabs.pokemongo")
            time.sleep(1)
            if mitm_mapper is not None:
                mitm_mapper.collect_location_stats(self._origin, self.current_location, 1, time.time(), 4, 0,
                                                   self._mapping_manager.routemanager_get_mode(
                                                       self._routemanager_name),
                                                   99)
            return self._restart_pogo_safe()
        else:
            return False

    def _reopenRaidTab(self):
        logger.debug("_reopenRaidTab: Taking screenshot...")
        logger.debug(
            "reopenRaidTab: Attempting to retrieve screenshot before checking raidtab")
        if not self._takeScreenshot():
            logger.debug("_reopenRaidTab: Failed getting screenshot...")
            logger.error(
                "reopenRaidTab: Failed retrieving screenshot before checking for closebutton")
            return
        logger.debug("_reopenRaidTab: Checking close except nearby...")
        pathToPass = self.get_screenshot_path()
        logger.debug("Path: {}", str(pathToPass))
        self._pogoWindowManager.check_close_except_nearby_button(
            pathToPass, self._origin, self._communicator, 'True')
        logger.debug("_reopenRaidTab: Getting to raidscreen...")
        self._getToRaidscreen(3)
        time.sleep(1)

    def _get_trash_positions(self, full_screen=False):
        logger.debug("_get_trash_positions: Get_trash_position.")
        if not self._takeScreenshot(delayBefore=self.get_devicesettings_value("post_screenshot_delay", 1)):
            logger.debug("_get_trash_positions: Failed getting screenshot")
            return None

        if os.path.isdir(self.get_screenshot_path()):
            logger.error(
                "_get_trash_positions: screenshot.png is not a file/corrupted")
            return None

        logger.debug("_get_trash_positions: checking screen")
        trashes = self._pogoWindowManager.get_trash_click_positions(self.get_screenshot_path(),
                                                                    full_screen=full_screen)

        return trashes

    def _takeScreenshot(self, delayAfter=0.0, delayBefore=0.0, errorscreen: bool = False):
        logger.debug("Taking screenshot...")
        time.sleep(delayBefore)
        compareToTime = time.time() - self._lastScreenshotTaken
        logger.debug("Last screenshot taken: {}",
                     str(self._lastScreenshotTaken))

        # TODO: area settings for jpg/png and quality?
        screenshot_type: ScreenshotType = ScreenshotType.JPEG
        if self.get_devicesettings_value("screenshot_type", "jpeg") == "png":
            screenshot_type = ScreenshotType.PNG

        screenshot_quality: int = self.get_devicesettings_value("screenshot_quality", 80)

        take_screenshot = self._communicator.get_screenshot(self.get_screenshot_path(fileaddon=errorscreen),
                                                            screenshot_quality, screenshot_type)

        if self._lastScreenshotTaken and compareToTime < 0.5:
            logger.error(
                "takeScreenshot: screenshot taken recently, returning immediately")
            logger.debug("Screenshot taken recently, skipping")
            return True

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
        from mapadroid.utils.image_utils import getImageHash
        screenHash = getImageHash(os.path.join(self.get_screenshot_path()))
        logger.debug("checkPogoFreeze: Old Hash: {}",
                     str(self._lastScreenHash))
        logger.debug("checkPogoFreeze: New Hash: {}", str(screenHash))
        if hamming_distance(str(self._lastScreenHash), str(screenHash)) < 4 and str(
                self._lastScreenHash) != '0':
            logger.debug(
                "checkPogoFreeze: New and old Screenshoot are the same - no processing")
            self._lastScreenHashCount += 1
            logger.debug("checkPogoFreeze: Same Screen Count: " +
                         str(self._lastScreenHashCount))
            if self._lastScreenHashCount >= 100:
                self._lastScreenHashCount = 0
                self._restart_pogo()
        else:
            self._lastScreenHash = screenHash
            self._lastScreenHashCount = 0

            logger.debug("_checkPogoFreeze: done")

    def _check_pogo_main_screen(self, maxAttempts, again=False):
        logger.debug(
            "_check_pogo_main_screen: Trying to get to the Mainscreen with {} max attempts...",
            str(maxAttempts))
        pogoTopmost = self._communicator.is_pogo_topmost()
        if not pogoTopmost:
            return False

        if not self._takeScreenshot(delayBefore=self.get_devicesettings_value("post_screenshot_delay", 1)):
            if again:
                logger.error(
                    "_check_pogo_main_screen: failed getting a screenshot again")
                return False
        attempts = 0

        screenshot_path = self.get_screenshot_path()
        if os.path.isdir(screenshot_path):
            logger.error(
                "_check_pogo_main_screen: screenshot.png/.jpg is not a file/corrupted")
            return False

        logger.debug("_check_pogo_main_screen: checking mainscreen")
        while not self._pogoWindowManager.check_pogo_mainscreen(screenshot_path, self._origin):
            logger.warning("_check_pogo_main_screen: not on Mainscreen...")
            if attempts == maxAttempts:
                # could not reach raidtab in given maxAttempts
                logger.error(
                    "_check_pogo_main_screen: Could not get to Mainscreen within {} attempts",
                    str(maxAttempts))
                return False

            found = self._pogoWindowManager.check_close_except_nearby_button(self.get_screenshot_path(),
                                                                             self._origin,
                                                                             self._communicator,
                                                                             close_raid=True)
            if found:
                logger.debug("_check_pogo_main_screen: Found (X) button (except nearby)")

            if not found and self._pogoWindowManager.look_for_button(screenshot_path, 2.20, 3.01,
                                                                     self._communicator):
                logger.debug("_check_pogo_main_screen: Found button (small)")
                found = True

            if not found and self._pogoWindowManager.look_for_button(screenshot_path, 1.05, 2.20,
                                                                     self._communicator):
                logger.debug("_check_pogo_main_screen: Found button (big)")
                time.sleep(5)
                found = True

            logger.debug("_check_pogo_main_screen: Previous checks found popups: {}", str(found))

            self._takeScreenshot(delayBefore=self.get_devicesettings_value("post_screenshot_delay", 1))

            attempts += 1
        logger.debug("_check_pogo_main_screen: done")
        return True

    def _check_pogo_main_screen_tr(self):
        logger.debug(
            "_check_pogo_main_screen_tr: Trying to get to the Mainscreen ")
        pogoTopmost = self._communicator.is_pogo_topmost()
        if not pogoTopmost:
            return False

        if not self._takeScreenshot(delayBefore=self.get_devicesettings_value("post_screenshot_delay", 1)):
            return False

        screenshot_path = self.get_screenshot_path()
        if os.path.isdir(screenshot_path):
            logger.error(
                "_check_pogo_main_screen_tr: screenshot.png/.jpg is not a file/corrupted")
            return False

        logger.debug("_check_pogo_main_screen_tr: checking mainscreen")
        if not self._pogoWindowManager.check_pogo_mainscreen(screenshot_path, self._origin):
            return False

        logger.debug("_check_pogo_main_screen_tr: done")
        return True

    def _checkPogoButton(self):
        logger.debug("checkPogoButton: Trying to find buttons")
        pogoTopmost = self._communicator.is_pogo_topmost()
        if not pogoTopmost:
            return False

        if not self._takeScreenshot(delayBefore=self.get_devicesettings_value("post_screenshot_delay", 1)):
            # TODO: again?
            # if again:
            #     logger.error("checkPogoButton: failed getting a screenshot again")
            #     return False
            # TODO: throw?
            logger.debug("checkPogoButton: Failed getting screenshot")
            return False
        attempts = 0

        if os.path.isdir(self.get_screenshot_path()):
            logger.error("checkPogoButton: screenshot.png is not a file/corrupted")
            return False

        logger.debug("checkPogoButton: checking for buttons")
        found = self._pogoWindowManager.look_for_button(self.get_screenshot_path(), 2.20, 3.01,
                                                        self._communicator)
        if found:
            time.sleep(1)
            logger.debug("checkPogoButton: Found button (small)")

        if not found and self._pogoWindowManager.look_for_button(self.get_screenshot_path(), 1.05, 2.20,
                                                                 self._communicator):
            logger.debug("checkPogoButton: Found button (big)")
            found = True

        logger.debug("checkPogoButton: done")
        return found

    def _wait_pogo_start_delay(self):
        delay_count: int = 0
        pogo_start_delay: int = self.get_devicesettings_value("post_pogo_start_delay", 60)
        logger.info('Waiting for pogo start: {} seconds', str(pogo_start_delay))

        while delay_count <= pogo_start_delay:
            if not self._mapping_manager.routemanager_present(self._routemanager_name) \
                    or self._stop_worker_event.is_set():
                logger.error("Worker {} get killed while waiting for pogo start", str(self._origin))
                raise InternalStopWorkerException
            time.sleep(1)
            delay_count += 1

    def _checkPogoClose(self, takescreen=True):
        logger.debug("checkPogoClose: Trying to find closeX")
        pogoTopmost = self._communicator.is_pogo_topmost()
        if not pogoTopmost:
            return False

        if takescreen:
            if not self._takeScreenshot(
                    delayBefore=self.get_devicesettings_value("post_screenshot_delay", 1)):
                logger.debug("checkPogoClose: Could not get screenshot")
                return False

        if os.path.isdir(self.get_screenshot_path()):
            logger.error("checkPogoClose: screenshot.png is not a file/corrupted")
            return False

        logger.debug("checkPogoClose: checking for CloseX")
        found = self._pogoWindowManager.check_close_except_nearby_button(self.get_screenshot_path(),
                                                                         self._origin,
                                                                         self._communicator)
        if found:
            time.sleep(1)
            logger.debug("checkPogoClose: Found (X) button (except nearby)")
            logger.debug("checkPogoClose: done")
            return True
        logger.debug("checkPogoClose: done")
        return False

    def _getToRaidscreen(self, maxAttempts, again=False):
        # check for any popups (including post login OK)
        logger.debug(
            "getToRaidscreen: Trying to get to the raidscreen with {} max attempts...", str(maxAttempts))
        pogoTopmost = self._communicator.is_pogo_topmost()
        if not pogoTopmost:
            return False

        self._checkPogoFreeze()
        if not self._takeScreenshot(delayBefore=self.get_devicesettings_value("post_screenshot_delay", 1)):
            if again:
                logger.error(
                    "getToRaidscreen: failed getting a screenshot again")
                return False
            self._getToRaidscreen(maxAttempts, True)
            logger.debug("getToRaidscreen: Got screenshot, checking GPS")
        attempts = 0

        if os.path.isdir(self.get_screenshot_path()):
            logger.error(
                "getToRaidscreen: screenshot.png is not a file/corrupted")
            return False

        # TODO: replace self._origin with device ID
        while self._pogoWindowManager.is_gps_signal_lost(self.get_screenshot_path(), self._origin):
            logger.debug("getToRaidscreen: GPS signal lost")
            time.sleep(1)
            self._takeScreenshot()
            logger.warning("getToRaidscreen: GPS signal error")
            self._redErrorCount += 1
            if self._redErrorCount > 3:
                logger.error(
                    "getToRaidscreen: Red error multiple times in a row, restarting")
                self._redErrorCount = 0
                self._restart_pogo()
                return False
        self._redErrorCount = 0
        logger.debug("getToRaidscreen: checking raidscreen")
        while not self._pogoWindowManager.check_raidscreen(self.get_screenshot_path(), self._origin,
                                                           self._communicator):
            logger.debug("getToRaidscreen: not on raidscreen...")
            if attempts > maxAttempts:
                # could not reach raidtab in given maxAttempts
                logger.error(
                    "getToRaidscreen: Could not get to raidtab within {} attempts", str(maxAttempts))
                return False
            self._checkPogoFreeze()
            # not using continue since we need to get a screen before the next round...
            found = self._pogoWindowManager.look_for_button(self.get_screenshot_path(), 2.20, 3.01,
                                                            self._communicator)
            if found:
                logger.debug("getToRaidscreen: Found button (small)")

            if not found and self._pogoWindowManager.check_close_except_nearby_button(
                    self.get_screenshot_path(),
                    self._origin, self._communicator):
                logger.debug(
                    "getToRaidscreen: Found (X) button (except nearby)")
                found = True

            if not found and self._pogoWindowManager.look_for_button(self.get_screenshot_path(), 1.05, 2.20,
                                                                     self._communicator):
                logger.debug("getToRaidscreen: Found button (big)")
                found = True

            logger.debug(
                "getToRaidscreen: Previous checks found popups: {}", str(found))
            if not found:
                logger.debug(
                    "getToRaidscreen: Previous checks found nothing. Checking nearby open")
                if self._pogoWindowManager.check_nearby(self.get_screenshot_path(), self._origin,
                                                        self._communicator):
                    return self._takeScreenshot(
                        delayBefore=self.get_devicesettings_value("post_screenshot_delay", 1))

            if not self._takeScreenshot(
                    delayBefore=self.get_devicesettings_value("post_screenshot_delay", 1)):
                return False

            attempts += 1
        logger.debug("getToRaidscreen: done")
        return True

    def _get_screen_size(self):
        if self._stop_worker_event.is_set():
            raise WebsocketWorkerRemovedException
        screen = self._communicator.get_screensize()
        if screen is None:
            raise WebsocketWorkerRemovedException
        screen = screen.strip().split(' ')
        self._screen_x = screen[0]
        self._screen_y = screen[1]
        x_offset = self.get_devicesettings_value("screenshot_x_offset", 0)
        y_offset = self.get_devicesettings_value("screenshot_y_offset", 0)
        logger.debug('Get Screensize of {}: X: {}, Y: {}, X-Offset: {}, Y-Offset: {}', str(
            self._origin), str(self._screen_x), str(self._screen_y), str(x_offset), str(y_offset))
        self._resocalc.get_x_y_ratio(
            self, self._screen_x, self._screen_y, x_offset, y_offset)

