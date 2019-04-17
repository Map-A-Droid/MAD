import os
import time
from shutil import copyfile
from threading import Event, Thread

from ocr.checkWeather import checkWeather
from utils.geo import get_distance_of_two_points_in_meters
from utils.logging import logger
from utils.madGlobals import (InternalStopWorkerException,
                              WebsocketWorkerRemovedException)
from utils.s2Helper import S2Helper

from .WorkerBase import WorkerBase


class WorkerOCR(WorkerBase):
    def _pre_work_loop(self):
        self.__speed_weather_check_thread = Thread(name='speedWeatherCheckThread%s' % self._id,
                                                   target=self._speed_weather_check_thread)
        self.__speed_weather_check_thread.daemon = False
        self.__speed_weather_check_thread.start()

    def _health_check(self):
        pass

    def _pre_location_update(self):
        self.__start_speed_weather_check_event.set()

    def _move_to_location(self):
        routemanager = self._walker_routemanager
        if routemanager is None:
            raise InternalStopWorkerException
        # get the distance from our current position (last) to the next gym (cur)
        distance = get_distance_of_two_points_in_meters(float(self.last_location.lat),
                                                        float(
                                                            self.last_location.lng),
                                                        float(
                                                            self.current_location.lat),
                                                        float(self.current_location.lng))
        logger.info('Moving {} meters to the next position',
                    round(distance, 2))
        speed = routemanager.settings.get("speed", 0)
        max_distance = routemanager.settings.get("max_distance", None)
        if (speed == 0 or
                (max_distance and 0 < max_distance < distance)
                or (self.last_location.lat == 0.0 and self.last_location.lng == 0.0)):
            logger.info("main: Teleporting...")
            self._communicator.setLocation(
                self.current_location.lat, self.current_location.lng, 0)
            # cur_time = math.floor(time.time())  # the time we will take as a starting point to wait for data...

            delay_used = self._devicesettings.get('post_teleport_delay', 7)
            # Test for cooldown / teleported distance TODO: check this block...
            if self._devicesettings.get('cool_down_sleep', False):
                if distance > 2500:
                    delay_used = 8
                elif distance > 5000:
                    delay_used = 10
                elif distance > 10000:
                    delay_used = 15
                logger.debug(
                    "Need more sleep after Teleport: {} seconds!", str(delay_used))
                # curTime = math.floor(time.time())  # the time we will take as a starting point to wait for data...

            if 0 < self._devicesettings.get('walk_after_teleport_distance', 0) < distance:
                # TODO: actually use to_walk for distance
                to_walk = get_distance_of_two_points_in_meters(float(self.current_location.lat),
                                                               float(
                                                                   self.current_location.lng),
                                                               float(
                                                                   self.current_location.lat) + 0.0001,
                                                               float(self.current_location.lng) + 0.0001)
                logger.info("Walking a bit: {}", str(to_walk))
                time.sleep(0.3)
                self._communicator.walkFromTo(self.current_location.lat, self.current_location.lng,
                                              self.current_location.lat + 0.0001, self.current_location.lng + 0.0001,
                                              11)
                logger.debug("Walking back")
                time.sleep(0.3)
                self._communicator.walkFromTo(self.current_location.lat + 0.0001, self.current_location.lng + 0.0001,
                                              self.current_location.lat, self.current_location.lng, 11)
                logger.debug("Done walking")
        else:
            logger.info("main: Walking...")
            self._communicator.walkFromTo(self.last_location.lat,
                                          self.last_location.lng,
                                          self.current_location.lat,
                                          self.current_location.lng, speed)
            # cur_time = math.floor(time.time())  # the time we will take as a starting point to wait for data...
            delay_used = self._devicesettings.get('post_walk_delay', 7)
        logger.info("Sleeping {}", str(delay_used))
        time.sleep(float(delay_used))
        cur_time = time.time()
        self._devicesettings["last_location"] = self.current_location
        self.last_location = self.current_location
        return cur_time, True

    def _post_move_location_routine(self, timestamp):
        # check if the speed_weather_check_thread signalled an abort by setting the stop_worker_event
        if self._stop_worker_event.is_set():
            raise InternalStopWorkerException
        logger.debug("Main: acquiring lock")
        self._work_mutex.acquire()
        logger.debug("main: Lock acquired")
        # TODO: takeScreenshot can throw, should we care about releasing locks or just cleanup everything else?
        if not self._takeScreenshot():
            self._work_mutex.release()
            logger.debug(
                "Worker: couldn't take screenshot before radscreen check, lock released")
            return

        logger.debug("Worker: Got screenshot")
        # curTime = time.time()
        logger.info(
            "main: Checking raidcount and copying raidscreen if raids present")
        count_of_raids = self._pogoWindowManager.readRaidCircles(os.path.join(
            self._applicationArgs.temp_path, 'screenshot%s.png' % str(self._id)), self._id, self._communicator)
        if count_of_raids == -1:
            logger.debug("Worker: Count present but no raid shown")
            logger.warning(
                "main: Count present but no raid shown, reopening raidTab")
            self._reopenRaidTab()
            logger.debug("Done reopening raidtab")
            if not self._takeScreenshot():
                self._work_mutex.release()
                logger.debug(
                    "Worker: couldn't take screenshot after opening raidtab, lock released")
                return
            count_of_raids = self._pogoWindowManager.readRaidCircles(os.path.join(
                self._applicationArgs.temp_path, 'screenshot%s.png' % str(self._id)), self._id, self._communicator)
        #    elif countOfRaids == 0:
        #        emptycount += 1
        #        if emptycount > 30:
        #            emptycount = 0
        #            logger.error("Had 30 empty scans, restarting pogo")
        #            restartPogo()

        # not an elif since we may have gotten a new screenshot..
        # detectin weather
        if self._applicationArgs.weather:
            logger.debug("Worker: Checking weather...")
            weather = checkWeather(os.path.join(
                self._applicationArgs.temp_path, 'screenshot%s.png' % str(self._id)))
            if weather[0]:
                logger.debug('Submit Weather')
                cell_id = S2Helper.lat_lng_to_cell_id(
                    self.current_location.lat, self.current_location.lng)
                self._db_wrapper.update_insert_weather(
                    cell_id, weather[1], timestamp)
            else:
                logger.error('Weather could not detected')

        if count_of_raids > 0:
            logger.debug("Worker: Count of raids >0")
            logger.debug(
                "main: New und old Screenshoot are different - starting OCR")
            logger.debug("main: countOfRaids: {}", str(count_of_raids))
            timestamp = time.time()
            copyFileName = self._applicationArgs.raidscreen_path + '/raidscreen_' + str(timestamp) \
                + "_" + str(self.current_location.lat) + "_" + str(self.current_location.lng) + "_" \
                + str(count_of_raids) + '.png'
            logger.debug('Copying file: ' + copyFileName)
            logger.debug("Worker: Copying file to {}", str(copyFileName))
            copyfile(os.path.join(self._applicationArgs.temp_path,
                                  'screenshot%s.png' % str(self._id)), copyFileName)
            os.remove(os.path.join(self._applicationArgs.temp_path,
                                   'screenshot%s.png' % str(self._id)))

        logger.debug("main: Releasing lock")
        self._work_mutex.release()
        logger.debug("Worker: Lock released")

    def _start_pogo(self):
        pogoTopmost = self._communicator.isPogoTopmost()
        if pogoTopmost:
            return True

        if not self._communicator.isScreenOn():
            self._communicator.startApp("de.grennith.rgc.remotegpscontroller")
            logger.warning("Turning screen on")
            self._communicator.turnScreenOn()
            time.sleep(self._devicesettings.get(
                "post_turn_screen_on_delay", 7))

        curTime = time.time()
        startResult = False
        while not pogoTopmost:
            startResult = self._communicator.startApp(
                "com.nianticlabs.pokemongo")
            time.sleep(1)
            pogoTopmost = self._communicator.isPogoTopmost()
        reachedRaidtab = False
        if startResult:
            logger.warning("startPogo: Starting pogo...")
            time.sleep(self._devicesettings.get("post_pogo_start_delay", 60))
            self._last_known_state["lastPogoRestart"] = curTime

            # let's handle the login and stuff
            reachedRaidtab = self._getToRaidscreen(15, True)

        return reachedRaidtab

    def _cleanup(self):
        pass

    def _valid_modes(self):
        return ["raids_ocr"]

    def _speed_weather_check_thread(self):
        while not self._stop_worker_event.is_set():
            while not self.__start_speed_weather_check_event.is_set():
                time.sleep(0.5)
            if self._stop_worker_event.is_set():
                return
            logger.debug("checkSpeedWeatherWarningThread: acquiring lock")
            logger.debug("Speedweather: acquiring lock")
            self._work_mutex.acquire()
            try:
                logger.debug("Speedweather: acquired lock")
                logger.debug("checkSpeedWeatherWarningThread: lock acquired")

                logger.debug(
                    "checkSpeedWeatherWarningThread: Checking if pogo is running...")
                if not self._communicator.isPogoTopmost():
                    logger.warning(
                        "checkSpeedWeatherWarningThread: Starting Pogo")
                    self._restart_pogo()

                reached_raidscreen = self._getToRaidscreen(10, True)

                if reached_raidscreen:
                    logger.debug(
                        "checkSpeedWeatherWarningThread: checkSpeedWeatherWarningThread: reached raidscreen...")
                    self.__start_speed_weather_check_event.clear()
                else:
                    logger.debug(
                        "checkSpeedWeatherWarningThread: did not reach raidscreen in 10 attempts")
                    self.__start_speed_weather_check_event.set()
            except WebsocketWorkerRemovedException as e:
                logger.error(
                    "Timeout during init of worker {} with {}", str(self._id), str(e))
                self._stop_worker_event.set()
                self._work_mutex.release()
                return
            logger.debug("checkSpeedWeatherWarningThread: releasing lock")
            self._work_mutex.release()
            logger.debug("Speedweather: released lock")
            time.sleep(1)

    def __init__(self, args, id, lastKnownState, websocketHandler, walker_routemanager,
                 devicesettings, db_wrapper, pogoWindowManager, walker):
        WorkerBase.__init__(self, args, id, lastKnownState, websocketHandler,
                            walker_routemanager, devicesettings, db_wrapper=db_wrapper,
                            pogoWindowManager=pogoWindowManager, walker=walker)
        self.__speed_weather_check_thread = None
        self.__start_speed_weather_check_event = Event()
