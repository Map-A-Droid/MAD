import logging
import os
import time
from shutil import copyfile
from threading import Lock, Event, Thread, current_thread

from ocr.checkWeather import checkWeather
from utils.collections import Location
from utils.madGlobals import WebsocketWorkerRemovedException, MadGlobals
from utils.geo import get_distance_of_two_points_in_meters
from utils.s2Helper import S2Helper
from .WorkerBase import WorkerBase

log = logging.getLogger(__name__)


# communicator is the parent websocket, it also stores when a location update has last been sent to the worker
# build 2 threads. Thread A simply checks for popups etc, Thread B sets locationupdates with given delays if Thread A
# signals that the raid tab is open
class WorkerOcr(WorkerBase):
    def __init__(self, args, id, lastKnownState, websocketHandler, route_manager_daytime, route_manager_nighttime,
                 devicesettings, db_wrapper):
        WorkerBase.__init__(self, args, id, lastKnownState, websocketHandler, route_manager_daytime,
                            route_manager_nighttime, devicesettings, db_wrapper=db_wrapper)
        self.id = id
        self._workMutex = Lock()
        self._run_warning_thread_event = Event()
        self._locationCount = 0

    def _start_pogo(self):
        pogoTopmost = self._communicator.isPogoTopmost()
        if pogoTopmost:
            return True

        if not self._communicator.isScreenOn():
            self._communicator.startApp("de.grennith.rgc.remotegpscontroller")
            log.warning("Turning screen on")
            self._communicator.turnScreenOn()
            time.sleep(self._devicesettings.get("post_turn_screen_on_delay", 7))
            
        curTime = time.time()
        startResult = False
        while not pogoTopmost:
            startResult = self._communicator.startApp("com.nianticlabs.pokemongo")
            time.sleep(1)
            pogoTopmost = self._communicator.isPogoTopmost()
        reachedRaidtab = False
        if startResult:
            log.warning("startPogo: Starting pogo...")
            time.sleep(self._devicesettings.get("post_pogo_start_delay", 60))
            self._last_known_state["lastPogoRestart"] = curTime

            # let's handle the login and stuff
            reachedRaidtab = self._getToRaidscreen(15, True)

        return reachedRaidtab

    # TODO: update state...
    def _main_work_thread(self):
        current_thread().name = self.id
        log.debug("Sub called")
        # first check if pogo is running etc etc
        self._workMutex.acquire()
        try:
            self._initRoutine()
        except WebsocketWorkerRemovedException:
            log.error("Timeout during init of worker %s" % str(self.id))
            self._stop_worker_event.set()
            self._workMutex.release()
            return
        self._workMutex.release()
        # loop = asyncio.get_event_loop()
        # TODO:loop.create_task(self._speed_weather_check_thread())

        speedWeatherCheckThread = Thread(name='speedWeatherCheckThread%s' % self.id, target=self._speed_weather_check_thread)
        speedWeatherCheckThread.daemon = False
        speedWeatherCheckThread.start()

        currentLocation = self._last_known_state.get("last_location", None)
        if currentLocation is None:
            currentLocation = Location(0.0, 0.0)
        lastLocation = None
        while not self._stop_worker_event.isSet():
            while MadGlobals.sleep and self._route_manager_nighttime is None:
                time.sleep(1)
            __time = time.time()
            log.debug("Worker: acquiring lock for restart check")
            self._workMutex.acquire()
            log.debug("Worker: acquired lock")
            # Restart pogo every now and then...
            if self._devicesettings.get("restart_pogo", 80) > 0:
                # log.debug("main: Current time - lastPogoRestart: %s" % str(curTime - lastPogoRestart))
                # if curTime - lastPogoRestart >= (args.restart_pogo * 60):
                self._locationCount += 1
                if self._locationCount > self._devicesettings.get("restart_pogo", 80):
                    log.error("scanned " + str(self._devicesettings.get("restart_pogo", 80)) + " locations, restarting pogo")
                    try:
                        self._restartPogo()
                    except WebsocketWorkerRemovedException:
                        log.error("Timeout restarting pogo on %s" % str(self.id))
                        self._stop_worker_event.set()
                        self._workMutex.release()
                        return
                    self._locationCount = 0
            self._workMutex.release()
            log.debug("Worker: lock released")

            # TODO: consider adding runWarningThreadEvent.set()
            lastLocation = currentLocation
            self._last_known_state["last_location"] = lastLocation
            if MadGlobals.sleep:
                currentLocation = self._route_manager_nighttime.get_next_location()
                settings = self._route_manager_nighttime.settings
            else:
                currentLocation = self._route_manager_daytime.get_next_location()
                settings = self._route_manager_daytime.settings

            # TODO: set position... needs to be adjust for multidevice
            
            posfile = open(self.id+'.position', "w")
            posfile.write(str(currentLocation.lat)+", "+str(currentLocation.lng))
            posfile.close()

            log.debug("main: next stop: %s" % (str(currentLocation)))
            log.debug('main: LastLat: %s, LastLng: %s, CurLat: %s, CurLng: %s' %
                      (lastLocation.lat, lastLocation.lng,
                       currentLocation.lat, currentLocation.lng))
            # get the distance from our current position (last) to the next gym (cur)
            distance = get_distance_of_two_points_in_meters(float(lastLocation.lat), float(lastLocation.lng),
                                                            float(currentLocation.lat), float(currentLocation.lng))
            log.info('main: Moving %s meters to the next position' % distance)
            delayUsed = 0
            if MadGlobals.sleep:
                speed = self._route_manager_nighttime.settings.get("speed", 0)
            else:
                speed = self._route_manager_daytime.settings.get("speed", 0)
            if (speed == 0 or
                    (settings["max_distance"] and 0 < settings["max_distance"] < distance)
                    or (lastLocation.lat == 0.0 and lastLocation.lng == 0.0)):
                log.info("main: Teleporting...")
                try:
                    self._communicator.setLocation(currentLocation.lat, currentLocation.lng, 0)
                except WebsocketWorkerRemovedException:
                    log.error("Timeout setting location of %s" % str(self.id))
                    self._stop_worker_event.set()
                    return
                delayUsed = self._devicesettings.get("post_teleport_delay",7)
                # Test for cooldown / teleported distance TODO: check this block...
                if self._devicesettings.get("cool_down_sleep",False):
                    if distance > 2500:
                        delayUsed = 30
                    elif distance > 5000:
                        delayUsed = 45
                    elif distance > 10000:
                        delayUsed = 60
                    log.info("Need more sleep after Teleport: %s seconds!" % str(delayUsed))

                if 0 < self._devicesettings.get("walk_after_teleport_distance",0) < distance:
                    toWalk = get_distance_of_two_points_in_meters(float(currentLocation.lat), float(currentLocation.lng),
                                                                  float(currentLocation.lat) + 0.0001,
                                                                  float(currentLocation.lng) + 0.0001)
                    log.info("Walking a bit: %s" % str(toWalk))
                    time.sleep(0.3)
                    try:
                        self._communicator.walkFromTo(currentLocation.lat, currentLocation.lng,
                                                       currentLocation.lat + 0.0001, currentLocation.lng + 0.0001, 11)
                        log.debug("Walking back")
                        time.sleep(0.3)
                        self._communicator.walkFromTo(currentLocation.lat + 0.0001, currentLocation.lng + 0.0001,
                                                       currentLocation.lat, currentLocation.lng, 11)
                    except WebsocketWorkerRemovedException:
                        log.error("Timeout walking a bit on %s" % str(self.id))
                        self._stop_worker_event.set()
                        return
                    log.debug("Done walking")
            else:
                log.info("main: Walking...")
                try:
                    self._communicator.walkFromTo(lastLocation.lat, lastLocation.lng,
                                                  currentLocation.lat, currentLocation.lng,
                                                  speed)
                except WebsocketWorkerRemovedException:
                    log.error("Timeout while walking with worker %s" % str(self.id))
                    self._stop_worker_event.set()
                    return
                delayUsed = self._devicesettings.get("post_walk_delay",7)
            log.info("Sleeping %s" % str(delayUsed))
            time.sleep(float(delayUsed))

            log.debug("main: Acquiring lock")

            while MadGlobals.sleep: # or not runWarningThreadEvent.isSet():
                time.sleep(0.1)
            log.debug("Worker: acquiring lock")
            self._workMutex.acquire()
            log.debug("main: Lock acquired")
            try:
                if not self._takeScreenshot():
                    self._workMutex.release()
                    log.debug("Worker: Lock released")
                    continue
            except WebsocketWorkerRemovedException:
                log.error("Timeout grabbing a screenshot from %s" % str(self.id))
                self._stop_worker_event.set()
                self._workMutex.release()
                return
            log.debug("Worker: Got screenshot")
            curTime = time.time()
            if self._applicationArgs.last_scanned:
                log.info('main: Set new scannedlocation in Database')
                self._db_wrapper.set_scanned_location(str(currentLocation.lat), str(currentLocation.lng), str(curTime))
            log.info("main: Checking raidcount and copying raidscreen if raids present")
            countOfRaids = self._pogoWindowManager.readRaidCircles(os.path.join(
                self._applicationArgs.temp_path, 'screenshot%s.png' % str(self.id)), self.id)
            if countOfRaids == -1:
                log.debug("Worker: Count present but no raid shown")
                log.warning("main: Count present but no raid shown, reopening raidTab")
                try:
                    self._reopenRaidTab()
                except WebsocketWorkerRemovedException:
                    log.error("Timeout reopening the raidtab on %s" % str(self.id))
                    self._stop_worker_event.set()
                    self._workMutex.release()
                    return
                # tabOutAndInPogo()
                log.debug("Done reopening raidtab")
                try:
                    if not self._takeScreenshot():
                        self._workMutex.release()
                        log.debug("Worker: Lock released")
                        continue
                except WebsocketWorkerRemovedException:
                    log.error("Timeout grabbing screenshot from worker %s" % str(self.id))
                    self._stop_worker_event.set()
                    self._workMutex.release()
                    return
                countOfRaids = self._pogoWindowManager.readRaidCircles(os.path.join(
                    self._applicationArgs.temp_path, 'screenshot%s.png' % str(self.id)), self.id)
            #    elif countOfRaids == 0:
            #        emptycount += 1
            #        if emptycount > 30:
            #            emptycount = 0
            #            log.error("Had 30 empty scans, restarting pogo")
            #            restartPogo()

            # not an elif since we may have gotten a new screenshot..
            # detectin weather
            if self._applicationArgs.weather:
                log.debug("Worker: Checking weather...")
                weather = checkWeather(os.path.join(self._applicationArgs.temp_path, 'screenshot%s.png' % str(self.id)))
                if weather[0]:
                    log.debug('Submit Weather')
                    cell_id = S2Helper.lat_lng_to_cell_id(currentLocation.lat, currentLocation.lng)
                    self._db_wrapper.update_insert_weather(cell_id, weather[1], curTime)
                else:
                    log.error('Weather could not detected')

            if countOfRaids > 0:
                log.debug("Worker: Count of raids >0")
                log.debug("main: New und old Screenshoot are different - starting OCR")
                log.debug("main: countOfRaids: %s" % str(countOfRaids))
                curTime = time.time()
                copyFileName = self._applicationArgs.raidscreen_path + '/raidscreen_' + str(curTime) \
                               + "_" + str(currentLocation.lat) + "_" + str(currentLocation.lng) + "_" \
                               + str(countOfRaids) + '.png'
                log.debug('Copying file: ' + copyFileName)
                log.debug("Worker: Copying file to %s" % str(copyFileName))
                copyfile(os.path.join(self._applicationArgs.temp_path, 'screenshot%s.png' % str(self.id)), copyFileName)
                os.remove(os.path.join(self._applicationArgs.temp_path, 'screenshot%s.png' % str(self.id)))

            log.debug("main: Releasing lock")
            self._workMutex.release()
            log.debug("Worker: Lock released")


    # TODO: update state...
    def _speed_weather_check_thread(self):
        while not self._stop_worker_event.is_set():
            while MadGlobals.sleep:
                time.sleep(0.5)
            log.debug("checkSpeedWeatherWarningThread: acquiring lock")
            log.debug("Speedweather: acquiring lock")
            self._workMutex.acquire()
            try:
                log.debug("Speedweather: acquired lock")
                log.debug("checkSpeedWeatherWarningThread: lock acquired")

                log.debug("checkSpeedWeatherWarningThread: Checking if pogo is running...")
                try:
                    if not self._communicator.isPogoTopmost():
                        log.warning("checkSpeedWeatherWarningThread: Starting Pogo")
                        self._restartPogo()
                except WebsocketWorkerRemovedException:
                    log.error("Timeout checking if pogo is topmost/restarting pogo on %s" % str(self.id))
                    self._stop_worker_event.set()
                    self._workMutex.release()
                    return

                try:
                    reachedRaidscreen = self._getToRaidscreen(10, True)
                except WebsocketWorkerRemovedException:
                    log.error("Timeout getting to raidscreen on %s" % str(self.id))
                    self._stop_worker_event.set()
                    self._workMutex.release()
                    return
                if reachedRaidscreen:
                    log.debug("checkSpeedWeatherWarningThread: checkSpeedWeatherWarningThread: reached raidscreen...")
                    self._run_warning_thread_event.set()
                else:
                    log.debug("checkSpeedWeatherWarningThread: did not reach raidscreen in 10 attempts")
                    self._run_warning_thread_event.clear()
            except WebsocketWorkerRemovedException as e:
                log.error("Timeout during init of worker %s with %s" % (str(self.id), str(e)))
                self._stop_worker_event.set()
                self._workMutex.release()
                return
            log.debug("checkSpeedWeatherWarningThread: releasing lock")
            self._workMutex.release()
            log.debug("Speedweather: released lock")
            time.sleep(1)








