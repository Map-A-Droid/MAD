from threading import Lock

from mapadroid.utils import ScreenshotType
from mapadroid.utils import get_distance_of_two_points_in_meters
from mapadroid.utils.logging import logger


class Communicator:
    UPDATE_INTERVAL = 0.4

    def __init__(self, websocket_handler, worker_id: str, worker_instance_ref, command_timeout: float):
        # Throws ValueError if unable to connect!
        # catch in code using this class
        self.worker_id: str = worker_id
        self.worker_instance_ref = worker_instance_ref
        self.websocket_handler = websocket_handler
        self.__command_timeout: float = command_timeout
        self.__sendMutex = Lock()

    def cleanup_websocket(self):
        logger.info(
            "Communicator of {} acquiring lock to cleanup worker in websocket", str(self.worker_id))
        self.__sendMutex.acquire()
        try:
            logger.info("Communicator of {} calling cleanup", str(self.worker_id))
            self.websocket_handler.clean_up_user(
                self.worker_id, self.worker_instance_ref)
        finally:
            self.__sendMutex.release()

    def __runAndOk(self, command, timeout) -> bool:
        return self.__run_and_ok_bytes(command, timeout)

    def __run_and_ok_bytes(self, message, timeout: float, byte_command: int = None) -> bool:
        self.__sendMutex.acquire()
        try:
            result = self.websocket_handler.send_and_wait(
                self.worker_id, self.worker_instance_ref, message, timeout, byte_command=byte_command)
            return result is not None and "OK" == result.strip()
        finally:
            self.__sendMutex.release()

    def install_apk(self, filepath: str, timeout: float) -> bool:
        # TODO: check if file exists...
        with open(filepath, "rb") as file:  # opening for [r]eading as [b]inary
            data = file.read()  # if you only wanted to read 512 bytes, do .read(512)
        return self.__run_and_ok_bytes(message=data, timeout=timeout, byte_command=1)

    def startApp(self, package_name):
        return self.__runAndOk("more start {}\r\n".format(package_name), self.__command_timeout)

    def stopApp(self, package_name):
        if not self.__runAndOk("more stop {}\r\n".format(package_name), self.__command_timeout):
            logger.error(
                "Failed stopping {}, please check if SU has been granted", package_name)
            return False
        else:
            return True

    def passthrough(self, command):
        response = self.websocket_handler.send_and_wait(self.worker_id,
                                                        self.worker_instance_ref,
                                                        "passthrough {}".format(command),
                                                        self.__command_timeout)
        return response

    def reboot(self) -> bool:
        return self.__runAndOk("more reboot now\r\n", self.__command_timeout)

    def restartApp(self, package_name) -> bool:
        return self.__runAndOk("more restart {}\r\n".format(package_name), self.__command_timeout)

    def resetAppdata(self, package_name) -> bool:
        return self.__runAndOk("more reset {}\r\n".format(package_name), self.__command_timeout)

    def clearAppCache(self, package_name) -> bool:
        return self.__runAndOk("more cache {}\r\n".format(package_name), self.__command_timeout)

    def magisk_off(self, package_name) -> bool:
        return self.passthrough("su -c magiskhide --rm {}".format(package_name))

    def magisk_on(self, package_name) -> bool:
        return self.passthrough("su -c magiskhide --add {}".format(package_name))

    def turnScreenOn(self) -> bool:
        return self.__runAndOk("more screen on\r\n", self.__command_timeout)

    def click(self, x, y) -> bool:
        return self.__runAndOk("screen click {} {}\r\n".format(str(int(round(x))), str(int(round(y)))),
                               self.__command_timeout)

    def swipe(self, x1, y1, x2, y2):
        return self.websocket_handler.send_and_wait(
            self.worker_id, self.worker_instance_ref, "touch swipe {} {} {} {}\r\n".format(
                str(int(round(x1))), str(int(round(y1))), str(int(round(x2))), str(int(round(y2)))),
            self.__command_timeout)

    def touchandhold(self, x1, y1, x2, y2, time: int = 3000) -> bool:
        return self.__runAndOk("touch swipe {} {} {} {} {}".format(
            str(int(round(x1))), str(int(round(y1))), str(int(round(x2))), str(int(round(y2))),
            str(int(time)))
            , self.__command_timeout)

    def getscreensize(self) -> str:
        response = self.websocket_handler.send_and_wait(self.worker_id, self.worker_instance_ref,
                                                        "screen size",
                                                        self.__command_timeout)
        return response

    def uiautomator(self) -> str:
        response = self.websocket_handler.send_and_wait(self.worker_id, self.worker_instance_ref,
                                                        "more uiautomator",
                                                        self.__command_timeout)
        return response

    def get_screenshot(self, path, quality: int = 70,
                       screenshot_type: ScreenshotType = ScreenshotType.JPEG) -> bool:
        if quality < 10 or quality > 100:
            logger.error("Invalid quality value passed for screenshots")
            return False

        screenshot_type_str: str = "jpeg"
        if screenshot_type == ScreenshotType.PNG:
            screenshot_type_str = "png"

        self.__sendMutex.acquire()
        try:
            encoded = self.websocket_handler.send_and_wait(
                self.worker_id, self.worker_instance_ref,
                "screen capture {} {}\r\n".format(screenshot_type_str, quality),
                self.__command_timeout
            )
        finally:
            self.__sendMutex.release()
        if encoded is None:
            return False
        elif isinstance(encoded, str):
            logger.debug("Screenshot response not binary")
            if "KO: " in encoded:
                logger.error(
                    "get_screenshot: Could not retrieve screenshot. Make sure your RGC is updated.")
                return False
            elif "OK:" not in encoded:
                logger.error("get_screenshot: response not OK")
                return False
            return False
        else:
            logger.debug("Storing screenshot...")

            with open(path, "wb") as fh:
                fh.write(encoded)
            logger.debug("Done storing, returning")
            return True

    def backButton(self) -> bool:
        return self.__runAndOk("screen back\r\n", self.__command_timeout)

    def homeButton(self) -> bool:
        return self.__runAndOk("touch keyevent 3", self.__command_timeout)

    def enterButton(self) -> bool:
        return self.__runAndOk("touch keyevent 61", self.__command_timeout)

    def sendText(self, text):
        return self.__runAndOk("touch text " + str(text), self.__command_timeout)

    def isScreenOn(self) -> bool:
        self.__sendMutex.acquire()
        try:
            state = self.websocket_handler.send_and_wait(self.worker_id, self.worker_instance_ref,
                                                         "more state screen\r\n", self.__command_timeout)
            if state is None:
                return False
            return "on" in state
        finally:
            self.__sendMutex.release()

    def isPogoTopmost(self) -> bool:
        self.__sendMutex.acquire()
        try:
            topmost = self.websocket_handler.send_and_wait(self.worker_id, self.worker_instance_ref,
                                                           "more topmost app\r\n", self.__command_timeout)
            if topmost is None:
                return False
            return "com.nianticlabs.pokemongo" in topmost
        finally:
            self.__sendMutex.release()

    def topmostApp(self) -> str:
        self.__sendMutex.acquire()
        try:
            topmost = self.websocket_handler.send_and_wait(self.worker_id, self.worker_instance_ref,
                                                           "more topmost app\r\n", self.__command_timeout)
            if topmost is None:
                return False
            return topmost
        finally:
            self.__sendMutex.release()

    def setLocation(self, lat, lng, alt):
        self.__sendMutex.acquire()
        try:
            response = self.websocket_handler.send_and_wait(self.worker_id, self.worker_instance_ref,
                                                            "geo fix {} {} {}\r\n".format(
                                                                lat, lng, alt),
                                                            self.__command_timeout)
            return response
        finally:
            self.__sendMutex.release()

    def terminate_connection(self):
        self.__sendMutex.acquire()
        try:
            response = self.websocket_handler.send_and_wait(
                self.worker_id, self.worker_instance_ref, "exit\r\n", 5)
            return response
        finally:
            self.__sendMutex.release()

    # coords need to be float values
    # speed integer with km/h
    #######
    # This blocks!
    #######
    def walkFromTo(self, startLat, startLng, destLat, destLng, speed):
        with self.__sendMutex:
            # calculate the time it will take to walk and add it to the timeout!
            distance = get_distance_of_two_points_in_meters(
                startLat, startLng, destLat, destLng)
            # speed is in kmph, distance in m
            # we want m/s -> speed / 3.6
            speed_meters = speed / 3.6
            seconds_traveltime = distance / speed_meters
            response = self.websocket_handler.send_and_wait(self.worker_id, self.worker_instance_ref,
                                                            "geo walk {} {} {} {} {}\r\n".format(startLat,
                                                                                                 startLng,
                                                                                                 destLat,
                                                                                                 destLng,
                                                                                                 speed),
                                                            self.__command_timeout + seconds_traveltime)
            return response
