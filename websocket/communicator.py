from threading import Lock

import gpxdata
from utils.geo import get_distance_of_two_points_in_meters
from utils.logging import logger


class Communicator:
    UPDATE_INTERVAL = 0.4

    def __init__(self, websocketHandler, id, worker_instance_ref, commandTimeout):
        # Throws ValueError if unable to connect!
        # catch in code using this class
        self.id = id
        self.worker_instance_ref = worker_instance_ref
        self.websocketHandler = websocketHandler
        self.__commandTimeout = commandTimeout
        self.__sendMutex = Lock()

    def cleanup_websocket(self):
        logger.info(
            "Communicator of {} acquiring lock to cleanup worker in websocket", str(self.id))
        self.__sendMutex.acquire()
        try:
            logger.info("Communicator of {} calling cleanup", str(self.id))
            self.websocketHandler.clean_up_user(
                self.id, self.worker_instance_ref)
        finally:
            self.__sendMutex.release()

    def __runAndOk(self, command, timeout):
        self.__sendMutex.acquire()
        try:
            result = self.websocketHandler.send_and_wait(
                self.id, self.worker_instance_ref, command, timeout)
            return result is not None and "OK" in result
        finally:
            self.__sendMutex.release()

    def startApp(self, packageName):
        return self.__runAndOk("more start %s\r\n" % (packageName), self.__commandTimeout)

    def stopApp(self, packageName):
        if not self.__runAndOk("more stop %s\r\n" % (packageName), self.__commandTimeout):
            logger.error(
                "Failed stopping {}, please check if SU has been granted", packageName)
            return False
        else:
            return True

    def reboot(self):
        return self.__runAndOk("more reboot now\r\n", self.__commandTimeout)

    def restartApp(self, packageName):
        return self.__runAndOk("more restart %s\r\n" % (packageName), self.__commandTimeout)

    def resetAppdata(self, packageName):
        return self.__runAndOk("more reset %s\r\n" % (packageName), self.__commandTimeout)

    def clearAppCache(self, packageName):
        return self.__runAndOk("more cache %s\r\n" % (packageName), self.__commandTimeout)

    def turnScreenOn(self):
        return self.__runAndOk("more screen on\r\n", self.__commandTimeout)

    def click(self, x, y):
        return self.__runAndOk("screen click %s %s\r\n" % (str(int(round(x))), str(int(round(y)))),
                               self.__commandTimeout)

    def swipe(self, x1, y1, x2, y2):
        return self.websocketHandler.send_and_wait(self.id, self.worker_instance_ref, "touch swipe %s %s %s %s\r\n" % (
            str(int(round(x1))), str(int(round(y1))), str(int(round(x2))), str(int(round(y2)))), self.__commandTimeout)

    def touchandhold(self, x1, y1, x2, y2):
        return self.__runAndOk("touch swipe %s %s %s %s 3000" % (
            str(int(round(x1))), str(int(round(y1))), str(int(round(x2))), str(int(round(y2)))), self.__commandTimeout)

    def getscreensize(self):
        response = self.websocketHandler.send_and_wait(self.id, self.worker_instance_ref, "screen size",
                                                       self.__commandTimeout)
        return response

    def get_screenshot_single(self, path):
        self.__sendMutex.acquire()
        try:
            encoded = self.websocketHandler.send_and_wait(self.id, self.worker_instance_ref, "screen single\r\n",
                                                          self.__commandTimeout)
        finally:
            self.__sendMutex.release()
        if encoded is None:
            return False
        elif isinstance(encoded, str):
            logger.debug("Screenshot response not binary")
            if "KO: " in encoded:
                logger.error(
                    "getScreenshot: Could not retrieve screenshot. Check if mediaprojection is enabled!")
                return False
            elif "OK:" not in encoded:
                logger.error("getScreenshot: response not OK")
                return False
            return False
        else:
            logger.debug("Storing screenshot...")

            fh = open(path, "wb")
            fh.write(encoded)
            fh.close()
            logger.debug("Done storing, returning")
            return True

    def getScreenshot(self, path):
        self.__sendMutex.acquire()
        try:
            encoded = self.websocketHandler.send_and_wait(self.id, self.worker_instance_ref, "screen capture\r\n",
                                                          self.__commandTimeout)
        finally:
            self.__sendMutex.release()
        if encoded is None:
            return False
        elif isinstance(encoded, str):
            logger.debug("Screenshot response not binary")
            if "KO: " in encoded:
                logger.error(
                    "getScreenshot: Could not retrieve screenshot. Check if mediaprojection is enabled!")
                return False
            elif "OK:" not in encoded:
                logger.error("getScreenshot: response not OK")
                return False
            return False
        else:
            logger.debug("Storing screenshot...")

            fh = open(path, "wb")
            fh.write(encoded)
            fh.close()
            logger.debug("Done storing, returning")
            return True

    def backButton(self):
        return self.__runAndOk("screen back\r\n", self.__commandTimeout)

    def homeButton(self):
        return self.__runAndOk("touch keyevent 3", self.__commandTimeout)

    def sendText(self, text):
        return self.__runAndOk("touch text " + str(text), self.__commandTimeout)

    def isScreenOn(self):
        self.__sendMutex.acquire()
        try:
            state = self.websocketHandler.send_and_wait(self.id, self.worker_instance_ref, "more state screen\r\n",
                                                        self.__commandTimeout)
            if state is None:
                return False
            return "on" in state
        finally:
            self.__sendMutex.release()

    def isPogoTopmost(self):
        self.__sendMutex.acquire()
        try:
            topmost = self.websocketHandler.send_and_wait(self.id, self.worker_instance_ref, "more topmost app\r\n",
                                                          self.__commandTimeout)
            if topmost is None:

                return False
            return "com.nianticlabs.pokemongo" in topmost
        finally:
            self.__sendMutex.release()

    def setLocation(self, lat, lng, alt):
        self.__sendMutex.acquire()
        try:
            response = self.websocketHandler.send_and_wait(self.id, self.worker_instance_ref,
                                                           "geo fix %s %s %s\r\n" % (
                                                               lat, lng, alt),
                                                           self.__commandTimeout)
            return response
        finally:
            self.__sendMutex.release()

    def terminate_connection(self):
        self.__sendMutex.acquire()
        try:
            response = self.websocketHandler.send_and_wait(
                self.id, self.worker_instance_ref, "exit\r\n", 5)
            return response
        finally:
            self.__sendMutex.release()

    # coords need to be float values
    # speed integer with km/h
    #######
    # This blocks!
    #######
    def walkFromTo(self, startLat, startLng, destLat, destLng, speed):
        self.__sendMutex.acquire()
        # calculate the time it will take to walk and add it to the timeout!
        distance = get_distance_of_two_points_in_meters(
            startLat, startLng, destLat, destLng)
        # speed is in kmph, distance in m
        # we want m/s -> speed / 3.6
        speed_meters = speed / 3.6
        seconds_traveltime = distance / speed_meters
        try:
            response = self.websocketHandler.send_and_wait(self.id, self.worker_instance_ref,
                                                           "geo walk %s %s %s %s %s\r\n"
                                                           % (startLat, startLng, destLat, destLng, speed),
                                                           self.__commandTimeout + seconds_traveltime)
            return response
        finally:
            self.__sendMutex.release()
