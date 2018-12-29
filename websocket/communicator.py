import datetime
import logging
import time
from threading import Lock

import gpxdata

log = logging.getLogger(__name__)


class Communicator:
    UPDATE_INTERVAL = 0.4

    def __init__(self, websocketHandler, id, commandTimeout):
        # Throws ValueError if unable to connect!
        # catch in code using this class
        self.id = id
        self.websocketHandler = websocketHandler
        self.__commandTimeout = commandTimeout
        self.__sendMutex = Lock()

    def __runAndOk(self, command, timeout):
        self.__sendMutex.acquire()
        result = self.websocketHandler.sendAndWait(self.id, command, timeout)
        self.__sendMutex.release()
        return result is not None and "OK" in result

    def startApp(self, packageName):
        return self.__runAndOk("more start %s\r\n" % (packageName), self.__commandTimeout)

    def stopApp(self, packageName):
        if not self.__runAndOk("more stop %s\r\n" % (packageName), self.__commandTimeout):
            log.error("Failed stopping %s, please check if SU has been granted" % packageName)
            return False
        else:
            return True

    def restartApp(self, packageName):
        return self.__runAndOk("more restart %s\r\n" % (packageName), self.__commandTimeout)

    def resetAppdata(self, packageName):
        return self.__runAndOk("more reset %s\r\n" % (packageName), self.__commandTimeout)

    def clearAppCache(self, packageName):
        return self.__runAndOk("more cache %s\r\n" % (packageName), self.__commandTimeout)

    def turnScreenOn(self):
        return self.__runAndOk("more screen on\r\n", self.__commandTimeout)

    def click(self, x, y):
        return self.__runAndOk("screen click %s %s\r\n" % (str(int(round(x))), str(int(round(y)))), self.__commandTimeout)

    def getScreenshot(self, path):
        self.__sendMutex.acquire()
        encoded = self.websocketHandler.sendAndWait(self.id, "screen capture\r\n", self.__commandTimeout)
        self.__sendMutex.release()
        if encoded is None:
            return False
        elif isinstance(encoded, str):
            log.debug("Screenshot response not binary")
            if "KO: " in encoded:
                log.error("getScreenshot: Could not retrieve screenshot. Check if mediaprojection is enabled!")
                return False
            elif "OK:" not in encoded:
                log.error("getScreenshot: response not OK")
                return False
            return False
        else:
            log.debug("Storing screenshot...")

            fh = open(path, "wb")
            fh.write(encoded)
            fh.close()
            log.debug("Done storing, returning")
            return True

    def backButton(self):
        return self.__runAndOk("screen back\r\n", self.__commandTimeout)

    def isScreenOn(self):
        self.__sendMutex.acquire()
        state = self.websocketHandler.sendAndWait(self.id, "more state screen\r\n", self.__commandTimeout)
        self.__sendMutex.release()
        if state is None:
            return False
        return "on" in state

    def isPogoTopmost(self):
        self.__sendMutex.acquire()
        topmost = self.websocketHandler.sendAndWait(self.id, "more topmost app\r\n", self.__commandTimeout)
        self.__sendMutex.release()
        if topmost is None:
            return False
        return "com.nianticlabs.pokemongo" in topmost

    def setLocation(self, lat, lng, alt):
        self.__sendMutex.acquire()
        response = self.websocketHandler.sendAndWait(self.id, "geo fix %s %s %s\r\n" % (lat, lng, alt), self.__commandTimeout)
        self.__sendMutex.release()
        return response

    # coords need to be float values
    # speed integer with km/h
    #######
    # This blocks!
    #######
    def walkFromTo(self, startLat, startLng, destLat, destLng, speed):
        self.__sendMutex.acquire()
        response = self.websocketHandler.sendAndWait(self.id, "geo walk %s %s %s %s %s\r\n"
                                                     % (startLat, startLng, destLat, destLng, speed),
                                                     self.__commandTimeout)
        self.__sendMutex.release()
        return response
        # startLat = float(startLat)
        # startLng = float(startLng)
        # destLat = float(destLat)
        # destLng = float(destLng)
        # start = gpxdata.TrackPoint(startLat, startLng, 1.0, datetime.datetime(2010, 1, 1, 0, 0, 0))
        # dest = gpxdata.TrackPoint(destLat, destLng, 1.0, datetime.datetime(2010, 1, 1, 0, 0, 15))
        #
        # t_speed = None
        # if speed:
        #     t_speed = speed / 3.6
        # log.debug("walkFromTo: calling __walkTrackSpeed")
        # self.__walkTrackSpeed(start, t_speed, dest)

    # TODO: errorhandling, return value
    def __walkTrackSpeed(self, start, speed, dest):
        log.debug("__walkTrackSpeed: called, calculating distance and travel_time")
        distance = start.distance(dest)
        travel_time = distance / speed

        if travel_time <= Communicator.UPDATE_INTERVAL:
            log.debug("__walkTrackSpeed: travel_time is <= UPDATE_INTERVAL")
            time.sleep(travel_time)

        log.debug("__walkTrackSpeed: starting to walk")
        while travel_time > Communicator.UPDATE_INTERVAL:
            log.debug("__walkTrackSpeed: sleeping for %s" % str(Communicator.UPDATE_INTERVAL))
            time.sleep(Communicator.UPDATE_INTERVAL)
            log.debug("__walkTrackSpeed: Next round")
            travel_time -= Communicator.UPDATE_INTERVAL
            # move GEOFIX_UPDATE_INTERVAL*speed meters
            # in straight line between last_point and point
            course = start.course(dest)
            distance = Communicator.UPDATE_INTERVAL * speed
            start = start + gpxdata.CourseDistance(course, distance)
            startLat = start.lat
            startLng = start.lon
            log.debug("__walkTrackSpeed: sending location")
            self.setLocation(repr(startLat), repr(startLng), "")
            log.debug("__walkTrackSpeed: done sending location")
