import asyncio
import functools
import math
import os
import time
from abc import abstractmethod
from threading import Event, Lock, Thread, current_thread
from typing import Optional
from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.mitm_receiver.MitmMapper import MitmMapper
from mapadroid.ocr.pogoWindows import PogoWindows
from mapadroid.ocr.screenPath import WordToScreenMatching
from mapadroid.ocr.screen_type import ScreenType
from mapadroid.utils import MappingManager
from mapadroid.utils.collections import Location
from mapadroid.utils.hamming import hamming_distance
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
from mapadroid.utils.logging import get_logger, LoggerEnums


logger = get_logger(LoggerEnums.worker)


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
        self._mode = self._mapping_manager.routemanager_get_mode(self._routemanager_name)
        self._levelmode = self._mapping_manager.routemanager_get_level(self._routemanager_name)
        self._geofencehelper = self._mapping_manager.routemanager_get_geofence_helper(self._routemanager_name)

        self.current_location = Location(0.0, 0.0)
        self.last_location = self.get_devicesettings_value("last_location", None)

        if self.last_location is None:
            self.last_location = Location(0.0, 0.0)

        if self.get_devicesettings_value('last_mode', None) is not None and \
                self.get_devicesettings_value('last_mode') in ("raids_mitm", "mon_mitm", "iv_mitm"):
            # Reset last_location - no useless waiting delays (otherwise stop mode)
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
        self.logger.debug("Fetching devicemappings")
        try:
            devicemappings: Optional[dict] = self._mapping_manager.get_devicemappings_of(self._origin)
        except (EOFError, FileNotFoundError) as e:
            self.logger.warning("Failed fetching devicemappings in with description: {}. Stopping worker", e)
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
            self.logger.info("Creating debugscreen: {}", screenshot_filename)

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
        t_main_work = Thread(name=self._origin,
                             target=self._main_work_thread)
        t_main_work.daemon = True
        t_main_work.start()
        # do some other stuff in the main process
        while not self._stop_worker_event.isSet():
            time.sleep(1)

        while t_main_work.is_alive():
            time.sleep(1)
            t_main_work.join()
        self.logger.info("Worker stopped gracefully")
        # async_result.get()
        return self._last_known_state

    def stop_worker(self):
        if self._stop_worker_event.set():
            self.logger.info('Worker already stopped - waiting for it')
        else:
            self._stop_worker_event.set()
            self.logger.warning("Worker stop called")

    def _internal_pre_work(self):
        current_thread().name = self._origin

        start_position = self.get_devicesettings_value("startcoords_of_walker", None)
        calc_type = self._mapping_manager.routemanager_get_calc_type(self._routemanager_name)

        if start_position and (self._levelmode and calc_type == "routefree"):
            startcoords = self.get_devicesettings_value("startcoords_of_walker").replace(' ', '') \
                .replace('_', '').split(',')

            if not self._geofencehelper.is_coord_inside_include_geofence(Location(
                    float(startcoords[0]), float(startcoords[1]))):
                self.logger.warning("Startcoords not in geofence - setting middle of fence as starting position")
                lat, lng = self._geofencehelper.get_middle_from_fence()
                start_position = str(lat) + "," + str(lng)

        if start_position is None and \
                (self._levelmode and calc_type == "routefree"):
            self.logger.warning("Starting level mode without worker start position")
            # setting coords
            lat, lng = self._geofencehelper.get_middle_from_fence()
            start_position = str(lat) + "," + str(lng)

        if start_position is not None:
            startcoords = start_position.replace(' ', '').replace('_', '').split(',')

            if not self._geofencehelper.is_coord_inside_include_geofence(Location(
                    float(startcoords[0]), float(startcoords[1]))):
                self.logger.warning("Startcoords not in geofence - setting middle of fence as startposition")
                lat, lng = self._geofencehelper.get_middle_from_fence()
                start_position = str(lat) + "," + str(lng)
                startcoords = start_position.replace(' ', '').replace('_', '').split(',')

            self.logger.info('Setting startcoords or walker lat {} / lng {}', startcoords[0], startcoords[1])
            self._communicator.set_location(Location(startcoords[0], startcoords[1]), 0)

            self._mapping_manager.set_worker_startposition(routemanager_name=self._routemanager_name,
                                                           worker_name=self._origin,
                                                           lat=float(startcoords[0]),
                                                           lon=float(startcoords[1]))

        with self._work_mutex:
            try:
                self._turn_screen_on_and_start_pogo()
                self._get_screen_size()
                # register worker  in routemanager
                self.logger.info("Try to register in Routemanager {}",
                                 self._mapping_manager.routemanager_get_name(self._routemanager_name))
                self._mapping_manager.register_worker_to_routemanager(self._routemanager_name, self._origin)
            except WebsocketWorkerRemovedException:
                self.logger.error("Timeout during init of worker")
                # no cleanup required here? TODO: signal websocket server somehow
                self._stop_worker_event.set()
                return

        self._async_io_looper_thread = Thread(name=self._origin,
                                              target=self._start_asyncio_loop)
        self._async_io_looper_thread.daemon = True
        self._async_io_looper_thread.start()

        self.loop_started.wait()
        self._pre_work_loop()

    def _internal_health_check(self):
        # check if pogo is topmost and start if necessary
        self.logger.debug4("_internal_health_check: Calling _start_pogo routine to check if pogo is topmost")
        pogo_started = False
        with self._work_mutex:
            self.logger.debug2("_internal_health_check: worker lock acquired")
            self.logger.debug4("Checking if we need to restart pogo")
            # Restart pogo every now and then...
            restart_pogo_setting = self.get_devicesettings_value("restart_pogo", 0)
            if restart_pogo_setting > 0:
                # self.logger.debug("main: Current time - lastPogoRestart: {}", str(curTime - lastPogoRestart))
                # if curTime - lastPogoRestart >= (args.restart_pogo * 60):
                if self._location_count > restart_pogo_setting:
                    self.logger.info("scanned {} locations, restarting game", restart_pogo_setting)
                    pogo_started = self._restart_pogo()
                    self._location_count = 0
                else:
                    pogo_started = self._start_pogo()
            else:
                pogo_started = self._start_pogo()

        self.logger.debug4("_internal_health_check: worker lock released")
        return pogo_started

    def _internal_cleanup(self):
        # set the event just to make sure - in case of exceptions for example
        self._stop_worker_event.set()
        try:
            self._mapping_manager.unregister_worker_from_routemanager(self._routemanager_name, self._origin)
        except ConnectionResetError as e:
            self.logger.warning("Failed unregistering from routemanager, routemanager may have stopped running already."
                                "Exception: {}", e)
        self.logger.info("Internal cleanup of started")
        self._cleanup()
        self.logger.info("Internal cleanup signaling end to websocketserver")

        if self._async_io_looper_thread is not None:
            self.logger.info("Stopping worker's asyncio loop")
            self.loop.call_soon_threadsafe(self.loop.stop)
            self._async_io_looper_thread.join()

        self._communicator.cleanup()

        self.logger.info("Internal cleanup of finished")

    def _main_work_thread(self):
        # TODO: signal websocketserver the removal
        try:
            self._internal_pre_work()
        except (InternalStopWorkerException, WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException,
                WebsocketWorkerConnectionClosedException):
            self.logger.error("Failed initializing worker, connection terminated exceptionally")
            self._internal_cleanup()
            return

        if not self.check_max_walkers_reached():
            self.logger.warning('Max. Walkers in Area {} - closing connections',
                                self._mapping_manager.routemanager_get_name(self._routemanager_name))
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
                self.logger.warning("Worker killed by walker settings")
                break

            try:
                # TODO: consider getting results of health checks and aborting the entire worker?
                self._internal_health_check()
                self._health_check()
            except (InternalStopWorkerException, WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException,
                    WebsocketWorkerConnectionClosedException):
                self.logger.error("Websocket connection to lost while running healthchecks, connection terminated "
                                  "exceptionally")
                break

            try:
                settings = self._internal_grab_next_location()
                if settings is None:
                    continue
            except (InternalStopWorkerException, WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException,
                    WebsocketWorkerConnectionClosedException):
                self.logger.warning("Worker of does not support mode that's to be run, connection terminated "
                                    "exceptionally")
                break

            try:
                self.logger.debug('Checking if new location is valid')
                valid = self._check_location_is_valid()
                if not valid:
                    break
            except (InternalStopWorkerException, WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException,
                    WebsocketWorkerConnectionClosedException):
                self.logger.warning("Worker received non valid coords!")
                break

            try:
                self._pre_location_update()
            except (InternalStopWorkerException, WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException,
                    WebsocketWorkerConnectionClosedException):
                self.logger.warning("Worker of stopping because of stop signal in pre_location_update, connection "
                                    "terminated exceptionally")
                break

            try:
                self.logger.debug2('LastLat: {}, LastLng: {}, CurLat: {}, CurLng: {}',
                                   self.get_devicesettings_value("last_location", Location(0, 0)).lat,
                                   self.get_devicesettings_value("last_location", Location(0, 0)).lng,
                                   self.current_location.lat, self.current_location.lng)
                time_snapshot, process_location = self._move_to_location()
            except (InternalStopWorkerException, WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException,
                    WebsocketWorkerConnectionClosedException):
                self.logger.warning("Worker failed moving to new location, stopping worker, connection terminated "
                                    "exceptionally")
                break

            if process_location:
                self._add_task_to_loop(self._update_position_file())
                self._location_count += 1
                if self._applicationArgs.last_scanned:
                    self.logger.debug("Seting new 'scannedlocation' in Database")
                    self._add_task_to_loop(self.update_scanned_location(
                        self.current_location.lat, self.current_location.lng, time_snapshot)
                    )

                try:
                    self._post_move_location_routine(time_snapshot)
                except (InternalStopWorkerException, WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException,
                        WebsocketWorkerConnectionClosedException):
                    self.logger.warning("Worker failed running post_move_location_routine, stopping worker")
                    break
                self.logger.info("Worker finished iteration, continuing work")

        self._internal_cleanup()

    async def _update_position_file(self):
        self.logger.debug2("Updating .position file")
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
            self.logger.error("Failed updating scanned location: {}", e)
            return

    def check_walker(self):
        mode = self._walker['walkertype']
        walkereventid = self._walker.get('eventid', None)
        if walkereventid is not None and walkereventid != self._event.get_current_event_id():
            self.logger.warning("A other Event has started - leaving now")
            return False
        if mode == "countdown":
            self.logger.info("Checking walker mode 'countdown'")
            countdown = self._walker['walkervalue']
            if not countdown:
                self.logger.error("No Value for Mode - check your settings! Killing worker")
                return False
            if self.workerstart is None:
                self.workerstart = math.floor(time.time())
            else:
                if math.floor(time.time()) >= int(self.workerstart) + int(countdown):
                    return False
            return True
        elif mode == "timer":
            self.logger.debug("Checking walker mode 'timer'")
            exittime = self._walker['walkervalue']
            if not exittime or ':' not in exittime:
                self.logger.error("No or wrong Value for Mode - check your settings! Killing worker")
                return False
            return check_walker_value_type(exittime)
        elif mode == "round":
            self.logger.debug("Checking walker mode 'round'")
            rounds = self._walker['walkervalue']
            if len(rounds) == 0:
                self.logger.error("No Value for Mode - check your settings! Killing worker")
                return False
            processed_rounds = self._mapping_manager.routemanager_get_rounds(self._routemanager_name,
                                                                             self._origin)
            if int(processed_rounds) >= int(rounds):
                return False
            return True
        elif mode == "period":
            self.logger.debug("Checking walker mode 'period'")
            period = self._walker['walkervalue']
            if len(period) == 0:
                self.logger.error("No Value for Mode - check your settings! Killing worker")
                return False
            return check_walker_value_type(period)
        elif mode == "coords":
            exittime = self._walker['walkervalue']
            if len(exittime) > 0:
                return check_walker_value_type(exittime)
            return True
        elif mode == "idle":
            self.logger.debug("Checking walker mode 'idle'")
            if len(self._walker['walkervalue']) == 0:
                self.logger.error("Wrong Value for mode - check your settings! Killing worker")
                return False
            sleeptime = self._walker['walkervalue']
            self.logger.info('going to sleep')
            killpogo = False
            if check_walker_value_type(sleeptime):
                self._stop_pogo()
                killpogo = True
            while not self._stop_worker_event.isSet() and check_walker_value_type(sleeptime):
                time.sleep(1)
            self.logger.info('just woke up')
            if killpogo:
                self._start_pogo()
            return False
        else:
            self.logger.error("Unknown walker mode! Killing worker")
            return False

    def set_geofix_sleeptime(self, sleeptime: int) -> bool:
        self._geofix_sleeptime = sleeptime
        return True

    def _internal_grab_next_location(self):
        # TODO: consider adding runWarningThreadEvent.set()
        self._last_known_state["last_location"] = self.last_location

        self.logger.debug("Requesting next location from routemanager")
        # requesting a location is blocking (iv_mitm will wait for a prioQ item), we really need to clean
        # the workers up...
        if int(self._geofix_sleeptime) > 0:
            self.logger.info('Getting a geofix position from MADMin - sleeping for {} seconds', self._geofix_sleeptime)
            time.sleep(int(self._geofix_sleeptime))
            self._geofix_sleeptime = 0

        self._check_for_mad_job()

        self.current_location = self._mapping_manager.routemanager_get_next_location(self._routemanager_name,
                                                                                     self._origin)
        return self._mapping_manager.routemanager_get_settings(self._routemanager_name)

    def _check_for_mad_job(self):
        if self.get_devicesettings_value("job", False):
            self.logger.info("Worker get a job - waiting")
            while self.get_devicesettings_value("job", False) and not self._stop_worker_event.is_set():
                time.sleep(10)
            self.logger.info("Worker processed the job and go on ")

    def _check_location_is_valid(self):
        if self.current_location is None:
            # there are no more coords - so worker is finished successfully
            self.set_devicesettings_value('finished', True)
            return None
        elif self.current_location is not None:
            self.logger.debug2('Coords are valid')
            return True

    def _turn_screen_on_and_start_pogo(self):
        if not self._communicator.is_screen_on():
            self._communicator.start_app("de.grennith.rgc.remotegpscontroller")
            self.logger.warning("Turning screen on")
            self._communicator.turn_screen_on()
            time.sleep(self.get_devicesettings_value("post_turn_screen_on_delay", 2))
        # check if pogo is running and start it if necessary
        self.logger.info("turnScreenOnAndStartPogo: (Re-)Starting Pogo")
        self._start_pogo()

    def _check_screen_on(self):
        if not self._communicator.is_screen_on():
            self._communicator.start_app("de.grennith.rgc.remotegpscontroller")
            self.logger.warning("Turning screen on")
            self._communicator.turn_screen_on()
            time.sleep(self.get_devicesettings_value("post_turn_screen_on_delay", 2))

    def _ensure_pogo_topmost(self):
        self.logger.info('Checking pogo screen...')

        while not self._stop_worker_event.is_set():
            screen_type: ScreenType = self._WordToScreenMatching.detect_screentype()
            if screen_type in [ScreenType.POGO, ScreenType.QUEST]:
                self._last_screen_type = screen_type
                self._loginerrorcounter = 0
                self.logger.debug2("Found pogo or questlog to be open")
                break

            if screen_type != ScreenType.ERROR and self._last_screen_type == screen_type:
                self._same_screen_count += 1
                self.logger.warning("Found {} multiple times in a row ({})", screen_type, self._same_screen_count)
                if self._same_screen_count > 3:
                    self.logger.warning("Screen is frozen!")
                    if self._same_screen_count > 4 or not self._restart_pogo():
                        self.logger.error("Restarting PoGo failed - reboot device")
                        self._reboot()
                    break
            elif self._last_screen_type != screen_type:
                self._same_screen_count = 0

            # now handle all screens that may not have been handled by detect_screentype since that only clicks around
            # so any clearing data whatsoever happens here (for now)
            if screen_type == ScreenType.UNDEFINED:
                self.logger.error("Undefined screentype!")
            elif screen_type == ScreenType.BLACK:
                self.logger.info("Found Black Loading Screen - waiting ...")
                time.sleep(20)
            elif screen_type == ScreenType.CLOSE:
                self.logger.debug("screendetection found pogo closed, start it...")
                self._start_pogo()
                self._loginerrorcounter += 1
            elif screen_type in [ScreenType.GAMEDATA, ScreenType.CONSENT]:
                self.logger.warning('Error getting Gamedata or strange ggl message appears')
                self._loginerrorcounter += 1
                if self._loginerrorcounter < 2:
                    self._restart_pogo_safe()
            elif screen_type == ScreenType.DISABLED:
                # Screendetection is disabled
                break
            elif screen_type == ScreenType.UPDATE:
                self.logger.warning(
                    'Found update pogo screen - sleeping 5 minutes for another check of the screen')
                # update pogo - later with new rgc version
                time.sleep(300)
            elif screen_type in [ScreenType.ERROR, ScreenType.FAILURE]:
                self.logger.warning('Something wrong with screendetection or pogo failure screen')
                self._loginerrorcounter += 1
            elif screen_type == ScreenType.NOGGL:
                self.logger.warning('Detected login select screen missing the Google'
                                    ' button - likely entered an invalid birthdate previously')
                self._loginerrorcounter += 1
            elif screen_type == ScreenType.GPS:
                self.logger.error("Detected GPS error - reboot device")
                self._reboot()
                break
            elif screen_type == ScreenType.SN:
                self.logger.warning('Getting SN Screen - restart PoGo and later PD')
                self._restart_pogo_safe()
                break

            if self._loginerrorcounter > 1:
                self.logger.error('Could not login again - (clearing game data + restarting device')
                self._stop_pogo()
                self._communicator.clear_app_cache("com.nianticlabs.pokemongo")
                if self.get_devicesettings_value('clear_game_data', False):
                    self.logger.info('Clearing game data')
                    self._communicator.reset_app_data("com.nianticlabs.pokemongo")
                self._loginerrorcounter = 0
                self._reboot()
                break

            self._last_screen_type = screen_type
        self.logger.info('Checking pogo screen is finished')
        return True

    def _restart_pogo_safe(self):
        self.logger.warning("WorkerBase::_restart_pogo_safe restarting pogo the long way")
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
        return self._start_pogo()

    def _switch_user(self):
        self.logger.info('Switching User - please wait ...')
        self._stop_pogo()
        time.sleep(5)
        self._communicator.reset_app_data("com.nianticlabs.pokemongo")
        self._turn_screen_on_and_start_pogo()
        if not self._ensure_pogo_topmost():
            self.logger.error('Kill Worker...')
            self._stop_worker_event.set()
            return False
        self.logger.info('Switching finished ...')
        return True

    def trigger_check_research(self):
        if "pokestops" in self._valid_modes():
            self.logger.warning("Cannot check for research menu while pokestops mode")
            return
        reached_main_menu = self._check_pogo_main_screen(3, True)
        if reached_main_menu:
            self._check_quest()
            time.sleep(2)
        return

    def _check_quest(self) -> ScreenType:
        self.logger.info('Precheck Quest Menu')
        questcounter: int = 0
        questloop: int = 0
        firstround: bool = True
        x, y = self._resocalc.get_coords_quest_menu(self)[0], self._resocalc.get_coords_quest_menu(self)[1]
        self._communicator.click(int(x), int(y))
        time.sleep(10)
        returncode: ScreenType = ScreenType.UNDEFINED
        if not self._takeScreenshot(delayBefore=self.get_devicesettings_value("post_screenshot_delay", 1),
                                    delayAfter=2):
            self.logger.error("_check_windows: Failed getting screenshot")
            return ScreenType.ERROR

        while not returncode == ScreenType.POGO and not self._stop_worker_event.isSet():
            returncode = self._WordToScreenMatching.checkQuest(self.get_screenshot_path())

            if returncode == ScreenType.QUEST:
                questcounter += 1
                if firstround:
                    self.logger.info('First round getting research menu')
                    x, y = (self._resocalc.get_close_main_button_coords(self)[0],
                            self._resocalc.get_close_main_button_coords(self)[1])
                    self._communicator.click(int(x), int(y))
                    time.sleep(1.5)
                    return ScreenType.POGO
                elif questcounter >= 2:
                    self.logger.info('Getting research menu two times in row')
                    x, y = (self._resocalc.get_close_main_button_coords(self)[0],
                            self._resocalc.get_close_main_button_coords(self)[1])
                    self._communicator.click(int(x), int(y))
                    time.sleep(1.5)
                    return ScreenType.POGO

            x, y = (self._resocalc.get_close_main_button_coords(self)[0],
                    self._resocalc.get_close_main_button_coords(self)[1])
            self._communicator.click(int(x), int(y))
            time.sleep(1.5)
            x, y = (self._resocalc.get_coords_quest_menu(self)[0],
                    self._resocalc.get_coords_quest_menu(self)[1])
            self._communicator.click(int(x), int(y))
            time.sleep(3)
            self._takeScreenshot(delayBefore=self.get_devicesettings_value("post_screenshot_delay", 1),
                                 delayAfter=2)
            if questloop > 5:
                self.logger.warning("Give up - maybe research screen is there...")
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
            self.logger.warning("Turning screen on")
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
            self.logger.success("startPogo: Started pogo successfully...")
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
            self.logger.error("Could not reboot due to client already disconnected")
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
        self.logger.debug("restartPogo: stop game resulted in {}", str(successful_stop))
        if successful_stop:
            if clear_cache:
                self._communicator.clear_app_cache("com.nianticlabs.pokemongo")
            time.sleep(1)
            if mitm_mapper is not None:
                mitm_mapper.collect_location_stats(self._origin, self.current_location, 1, time.time(), 4, 0,
                                                   self._mapping_manager.routemanager_get_mode(
                                                       self._routemanager_name),
                                                   99)
            return self._start_pogo()
        else:
            return False

    def _reopenRaidTab(self):
        self.logger.debug4("Attempting to retrieve screenshot before checking raidtab")
        if not self._takeScreenshot():
            self.logger.error("reopenRaidTab: Failed retrieving screenshot before checking for closebutton")
            return
        self.logger.debug2("Checking close except nearby...")
        pathToPass = self.get_screenshot_path()
        self.logger.debug2("Path: {}", str(pathToPass))
        self._pogoWindowManager.check_close_except_nearby_button(
            pathToPass, self._origin, self._communicator, 'True')
        self.logger.debug2("Getting to raidscreen...")
        self._getToRaidscreen(3)
        time.sleep(1)

    def _get_trash_positions(self, full_screen=False):
        self.logger.debug2("_get_trash_positions: Get_trash_position.")
        if not self._takeScreenshot(delayBefore=self.get_devicesettings_value("post_screenshot_delay", 1)):
            self.logger.debug("_get_trash_positions: Failed getting screenshot")
            return None

        if os.path.isdir(self.get_screenshot_path()):
            self.logger.error("_get_trash_positions: screenshot.png is not a file/corrupted")
            return None

        self.logger.debug2("_get_trash_positions: checking screen")
        trashes = self._pogoWindowManager.get_trash_click_positions(self._origin, self.get_screenshot_path(),
                                                                    full_screen=full_screen)

        return trashes

    def _takeScreenshot(self, delayAfter=0.0, delayBefore=0.0, errorscreen: bool = False):
        self.logger.debug2("Taking screenshot...")
        time.sleep(delayBefore)
        compareToTime = time.time() - self._lastScreenshotTaken
        self.logger.debug4("Last screenshot taken: {}", str(self._lastScreenshotTaken))

        # TODO: area settings for jpg/png and quality?
        screenshot_type: ScreenshotType = ScreenshotType.JPEG
        if self.get_devicesettings_value("screenshot_type", "jpeg") == "png":
            screenshot_type = ScreenshotType.PNG

        screenshot_quality: int = self.get_devicesettings_value("screenshot_quality", 80)

        take_screenshot = self._communicator.get_screenshot(self.get_screenshot_path(fileaddon=errorscreen),
                                                            screenshot_quality, screenshot_type)

        if self._lastScreenshotTaken and compareToTime < 0.5:
            self.logger.error("screenshot taken recently, returning immediately")
            return True

        elif not take_screenshot:
            self.logger.error("Failed retrieving screenshot")
            return False
        else:
            self.logger.debug("Success retrieving screenshot")
            self._lastScreenshotTaken = time.time()
            time.sleep(delayAfter)
            return True

    def _checkPogoFreeze(self):
        self.logger.debug("Checking if pogo froze")
        if not self._takeScreenshot():
            self.logger.debug("failed retrieving screenshot")
            return
        from mapadroid.utils.image_utils import getImageHash
        screenHash = getImageHash(os.path.join(self.get_screenshot_path()))
        self.logger.debug4("Old Hash: {}", self._lastScreenHash)
        self.logger.debug4("New Hash: {}", screenHash)
        if hamming_distance(str(self._lastScreenHash), str(screenHash)) < 4 and str(
                self._lastScreenHash) != '0':
            self.logger.debug("New and old Screenshoot are the same - no processing")
            self._lastScreenHashCount += 1
            self.logger.debug("Same Screen Count: {}", self._lastScreenHashCount)
            if self._lastScreenHashCount >= 100:
                self._lastScreenHashCount = 0
                self._restart_pogo()
        else:
            self._lastScreenHash = screenHash
            self._lastScreenHashCount = 0

            self.logger.debug("_checkPogoFreeze: done")

    def _check_pogo_main_screen(self, maxAttempts, again=False):
        self.logger.debug("_check_pogo_main_screen: Trying to get to the Mainscreen with {} max attempts...",
                          maxAttempts)
        pogoTopmost = self._communicator.is_pogo_topmost()
        if not pogoTopmost:
            return False

        if not self._takeScreenshot(delayBefore=self.get_devicesettings_value("post_screenshot_delay", 1)):
            if again:
                self.logger.error("_check_pogo_main_screen: failed getting a screenshot again")
                return False
        attempts = 0

        screenshot_path = self.get_screenshot_path()
        if os.path.isdir(screenshot_path):
            self.logger.error("_check_pogo_main_screen: screenshot.png/.jpg is not a file/corrupted")
            return False

        self.logger.debug("_check_pogo_main_screen: checking mainscreen")
        while not self._pogoWindowManager.check_pogo_mainscreen(screenshot_path, self._origin):
            self.logger.warning("_check_pogo_main_screen: not on Mainscreen...")
            if attempts == maxAttempts:
                # could not reach raidtab in given maxAttempts
                self.logger.error("_check_pogo_main_screen: Could not get to Mainscreen within {} attempts",
                                  maxAttempts)
                return False

            found = self._pogoWindowManager.check_close_except_nearby_button(self.get_screenshot_path(),
                                                                             self._origin,
                                                                             self._communicator,
                                                                             close_raid=True)
            if found:
                self.logger.debug("_check_pogo_main_screen: Found (X) button (except nearby)")

            if not found and self._pogoWindowManager.look_for_button(self._origin, screenshot_path, 2.20, 3.01,
                                                                     self._communicator):
                self.logger.debug("_check_pogo_main_screen: Found button (small)")
                found = True

            if not found and self._pogoWindowManager.look_for_button(self._origin, screenshot_path, 1.05, 2.20,
                                                                     self._communicator):
                self.logger.debug("_check_pogo_main_screen: Found button (big)")
                time.sleep(5)
                found = True

            self.logger.debug("_check_pogo_main_screen: Previous checks found pop ups: {}", found)

            self._takeScreenshot(delayBefore=self.get_devicesettings_value("post_screenshot_delay", 1))

            attempts += 1
        self.logger.debug("_check_pogo_main_screen: done")
        return True

    def _check_pogo_main_screen_tr(self):
        self.logger.debug("_check_pogo_main_screen_tr: Trying to get to the Main screen")
        pogoTopmost = self._communicator.is_pogo_topmost()
        if not pogoTopmost:
            return False

        if not self._takeScreenshot(delayBefore=self.get_devicesettings_value("post_screenshot_delay", 1)):
            return False

        screenshot_path = self.get_screenshot_path()
        if os.path.isdir(screenshot_path):
            self.logger.error("_check_pogo_main_screen_tr: screenshot.png/.jpg is not a file/corrupted")
            return False

        self.logger.debug("_check_pogo_main_screen_tr: checking mainscreen")
        if not self._pogoWindowManager.check_pogo_mainscreen(screenshot_path, self._origin):
            return False

        self.logger.debug("_check_pogo_main_screen_tr: done")
        return True

    def _checkPogoButton(self):
        self.logger.debug("checkPogoButton: Trying to find buttons")
        pogoTopmost = self._communicator.is_pogo_topmost()
        if not pogoTopmost:
            return False

        if not self._takeScreenshot(delayBefore=self.get_devicesettings_value("post_screenshot_delay", 1)):
            # TODO: again?
            # if again:
            #     self.logger.error("checkPogoButton: failed getting a screenshot again")
            #     return False
            # TODO: throw?
            self.logger.debug("checkPogoButton: Failed getting screenshot")
            return False
        if os.path.isdir(self.get_screenshot_path()):
            self.logger.error("checkPogoButton: screenshot.png is not a file/corrupted")
            return False

        self.logger.debug("checkPogoButton: checking for buttons")
        found = self._pogoWindowManager.look_for_button(self._origin, self.get_screenshot_path(), 2.20, 3.01,
                                                        self._communicator)
        if found:
            time.sleep(1)
            self.logger.debug("checkPogoButton: Found button (small)")

        if not found and self._pogoWindowManager.look_for_button(self._origin, self.get_screenshot_path(), 1.05, 2.20,
                                                                 self._communicator):
            self.logger.debug("checkPogoButton: Found button (big)")
            found = True

        self.logger.debug("checkPogoButton: done")
        return found

    def _wait_pogo_start_delay(self):
        delay_count: int = 0
        pogo_start_delay: int = self.get_devicesettings_value("post_pogo_start_delay", 60)
        self.logger.info('Waiting for pogo start: {} seconds', pogo_start_delay)

        while delay_count <= pogo_start_delay:
            if not self._mapping_manager.routemanager_present(self._routemanager_name) \
                    or self._stop_worker_event.is_set():
                self.logger.error("Killed while waiting for pogo start")
                raise InternalStopWorkerException
            time.sleep(1)
            delay_count += 1

    def _checkPogoClose(self, takescreen=True):
        self.logger.debug("checkPogoClose: Trying to find closeX")
        pogoTopmost = self._communicator.is_pogo_topmost()
        if not pogoTopmost:
            return False

        if takescreen:
            if not self._takeScreenshot(
                    delayBefore=self.get_devicesettings_value("post_screenshot_delay", 1)):
                self.logger.debug("checkPogoClose: Could not get screenshot")
                return False

        if os.path.isdir(self.get_screenshot_path()):
            self.logger.error("checkPogoClose: screenshot.png is not a file/corrupted")
            return False

        self.logger.debug("checkPogoClose: checking for CloseX")
        found = self._pogoWindowManager.check_close_except_nearby_button(self.get_screenshot_path(),
                                                                         self._origin,
                                                                         self._communicator)
        if found:
            time.sleep(1)
            self.logger.debug("checkPogoClose: Found (X) button (except nearby)")
            self.logger.debug("checkPogoClose: done")
            return True
        self.logger.debug("checkPogoClose: done")
        return False

    def _getToRaidscreen(self, maxAttempts, again=False):
        # check for any popups (including post login OK)
        self.logger.debug(
            "getToRaidscreen: Trying to get to the raidscreen with {} max attempts...", maxAttempts)
        pogoTopmost = self._communicator.is_pogo_topmost()
        if not pogoTopmost:
            return False

        self._checkPogoFreeze()
        if not self._takeScreenshot(delayBefore=self.get_devicesettings_value("post_screenshot_delay", 1)):
            if again:
                self.logger.error("getToRaidscreen: failed getting a screenshot again")
                return False
            self._getToRaidscreen(maxAttempts, True)
            self.logger.debug("getToRaidscreen: Got screenshot, checking GPS")
        attempts = 0

        if os.path.isdir(self.get_screenshot_path()):
            self.logger.error("getToRaidscreen: screenshot.png is not a file/corrupted")
            return False

        # TODO: replace self._origin with device ID
        while self._pogoWindowManager.is_gps_signal_lost(self.get_screenshot_path(), self._origin):
            self.logger.debug("getToRaidscreen: GPS signal lost")
            time.sleep(1)
            self._takeScreenshot()
            self.logger.warning("getToRaidscreen: GPS signal error")
            self._redErrorCount += 1
            if self._redErrorCount > 3:
                self.logger.error("getToRaidscreen: Red error multiple times in a row, restarting")
                self._redErrorCount = 0
                self._restart_pogo()
                return False
        self._redErrorCount = 0
        self.logger.debug("getToRaidscreen: checking raidscreen")
        while not self._pogoWindowManager.check_raidscreen(self.get_screenshot_path(), self._origin,
                                                           self._communicator):
            self.logger.debug("getToRaidscreen: not on raidscreen...")
            if attempts > maxAttempts:
                # could not reach raidtab in given maxAttempts
                self.logger.error("getToRaidscreen: Could not get to raidtab within {} attempts", maxAttempts)
                return False
            self._checkPogoFreeze()
            # not using continue since we need to get a screen before the next round...
            found = self._pogoWindowManager.look_for_button(self._origin, self.get_screenshot_path(), 2.20, 3.01,
                                                            self._communicator)
            if found:
                self.logger.debug("getToRaidscreen: Found button (small)")

            if not found and self._pogoWindowManager.check_close_except_nearby_button(
                    self.get_screenshot_path(),
                    self._origin, self._communicator):
                self.logger.debug("getToRaidscreen: Found (X) button (except nearby)")
                found = True

            if not found and self._pogoWindowManager.look_for_button(self._origin, self.get_screenshot_path(), 1.05,
                                                                     2.20, self._communicator):
                self.logger.debug("getToRaidscreen: Found button (big)")
                found = True

            self.logger.debug("getToRaidscreen: Previous checks found popups: {}", found)
            if not found:
                self.logger.debug("getToRaidscreen: Previous checks found nothing. Checking nearby open")
                if self._pogoWindowManager.check_nearby(self.get_screenshot_path(), self._origin,
                                                        self._communicator):
                    return self._takeScreenshot(
                        delayBefore=self.get_devicesettings_value("post_screenshot_delay", 1))

            if not self._takeScreenshot(
                    delayBefore=self.get_devicesettings_value("post_screenshot_delay", 1)):
                return False

            attempts += 1
        self.logger.debug("getToRaidscreen: done")
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
        self.logger.debug('Get Screensize: X: {}, Y: {}, X-Offset: {}, Y-Offset: {}', self._screen_x, self._screen_y,
                          x_offset, y_offset)
        self._resocalc.get_x_y_ratio(self, self._screen_x, self._screen_y, x_offset, y_offset)
