from threading import Lock
from typing import Optional

from mapadroid.utils.CustomTypes import MessageTyping
from mapadroid.utils.geo import get_distance_of_two_points_in_meters
from mapadroid.utils.logging import logger
from mapadroid.utils.madGlobals import ScreenshotType, WebsocketWorkerConnectionClosedException
from mapadroid.websocket.WebsocketConnectedClientEntry import WebsocketConnectedClientEntry


class Communicator:
    UPDATE_INTERVAL = 0.4

    def __init__(self, websocket_client_entry: WebsocketConnectedClientEntry, worker_id: str, worker_instance_ref,
                 command_timeout: float):
        # Throws ValueError if unable to connect!
        # catch in code using this class
        self.worker_id: str = worker_id
        self.worker_instance_ref = worker_instance_ref
        self.websocket_client_entry = websocket_client_entry
        self.__command_timeout: float = command_timeout
        self.__sendMutex = Lock()

    def cleanup_websocket(self):
        logger.info(
            "Communicator of {} calling exit to cleanup worker in websocket", str(self.worker_id))
        self.terminate_connection()

    def __runAndOk(self, command, timeout) -> bool:
        return self.__run_and_ok_bytes(command, timeout)

    def __run_get_gesponse(self, message: MessageTyping, timeout: float = None) -> Optional[MessageTyping]:
        with self.__sendMutex:
            timeout = self.__command_timeout if timeout is None else timeout
            return self.websocket_client_entry.send_and_wait(message, timeout=timeout,
                                                             worker_instance=self.worker_instance_ref)

    def __run_and_ok_bytes(self, message, timeout: float, byte_command: int = None) -> bool:
        with self.__sendMutex:
            result = self.websocket_client_entry.send_and_wait(message, timeout, self.worker_instance_ref,
                                                               byte_command=byte_command)
            return result is not None and "OK" == result.strip()

    def install_apk(self, timeout: float, filepath: str = None, data=None) -> bool:
        if not data:
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

    def passthrough(self, command) -> Optional[MessageTyping]:
        response = self.websocket_client_entry.send_and_wait("passthrough {}".format(command),
                                                             self.__command_timeout,
                                                             self.worker_instance_ref)
        return response

    def reboot(self) -> bool:
        return self.__runAndOk("more reboot now\r\n", self.__command_timeout)

    def restartApp(self, package_name) -> bool:
        return self.__runAndOk("more restart {}\r\n".format(package_name), self.__command_timeout)

    def resetAppdata(self, package_name) -> bool:
        return self.__runAndOk("more reset {}\r\n".format(package_name), self.__command_timeout)

    def clearAppCache(self, package_name) -> bool:
        return self.__runAndOk("more cache {}\r\n".format(package_name), self.__command_timeout)

    def magisk_off(self, package_name) -> None:
        self.passthrough("su -c magiskhide --rm {}".format(package_name))

    def magisk_on(self, package_name) -> None:
        self.passthrough("su -c magiskhide --add {}".format(package_name))

    def turnScreenOn(self) -> bool:
        return self.__runAndOk("more screen on\r\n", self.__command_timeout)

    def click(self, x, y) -> bool:
        return self.__runAndOk("screen click {} {}\r\n".format(str(int(round(x))), str(int(round(y)))),
                               self.__command_timeout)

    def swipe(self, x1, y1, x2, y2) -> Optional[MessageTyping]:
        return self.__run_get_gesponse("touch swipe {} {} {} {}\r\n".format(
                str(int(round(x1))), str(int(round(y1))), str(int(round(x2))), str(int(round(y2))))
        )

    def touchandhold(self, x1, y1, x2, y2, time: int = 3000) -> bool:
        return self.__runAndOk("touch swipe {} {} {} {} {}".format(
            str(int(round(x1))), str(int(round(y1))), str(int(round(x2))), str(int(round(y2))),
            str(int(time)))
            , self.__command_timeout)

    def getscreensize(self) -> Optional[MessageTyping]:
        return self.__run_get_gesponse("screen size")

    def uiautomator(self) -> str:
        return self.__run_get_gesponse("more uiautomator")

    def get_screenshot(self, path, quality: int = 70,
                       screenshot_type: ScreenshotType = ScreenshotType.JPEG) -> bool:
        if quality < 10 or quality > 100:
            logger.error("Invalid quality value passed for screenshots")
            return False

        screenshot_type_str: str = "jpeg"
        if screenshot_type == ScreenshotType.PNG:
            screenshot_type_str = "png"

        encoded = self.__run_get_gesponse("screen capture {} {}\r\n".format(screenshot_type_str, quality))
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
        state = self.__run_get_gesponse("more state screen\r\n")
        if state is None:
            return False
        return "on" in state

    def isPogoTopmost(self) -> bool:
        topmost = self.__run_get_gesponse("more topmost app\r\n")
        if topmost is None:
            return False
        return "com.nianticlabs.pokemongo" in topmost

    def topmostApp(self) -> Optional[MessageTyping]:
        return self.__run_get_gesponse("more topmost app\r\n")

    def setLocation(self, lat, lng, alt):
        return self.__run_get_gesponse("geo fix {} {} {}\r\n".format(lat, lng, alt))

    def terminate_connection(self):
        try:
            return self.__run_get_gesponse("exit\r\n", timeout=5)
        except WebsocketWorkerConnectionClosedException:
            logger.info("Cannot gracefully terminate connection of {}, it's already been closed", self.worker_id)

    # coords need to be float values
    # speed integer with km/h
    #######
    # This blocks!
    #######
    def walkFromTo(self, startLat, startLng, destLat, destLng, speed):
        # calculate the time it will take to walk and add it to the timeout!
        distance = get_distance_of_two_points_in_meters(
            startLat, startLng, destLat, destLng)
        # speed is in kmph, distance in m
        # we want m/s -> speed / 3.6
        speed_meters = speed / 3.6
        seconds_traveltime = distance / speed_meters
        return self.__run_get_gesponse("geo walk {} {} {} {} {}\r\n".format(startLat, startLng, destLat, destLng,
                                                                            speed),
                                       self.__command_timeout + seconds_traveltime)
