from threading import Lock
from typing import Optional

from mapadroid.utils.CustomTypes import MessageTyping
from mapadroid.utils.collections import Location
from mapadroid.utils.geo import get_distance_of_two_points_in_meters
from mapadroid.utils.logging import logger
from mapadroid.utils.madGlobals import ScreenshotType, WebsocketWorkerConnectionClosedException, \
    WebsocketWorkerTimeoutException
from mapadroid.websocket.AbstractCommunicator import AbstractCommunicator
from mapadroid.websocket.WebsocketConnectedClientEntry import WebsocketConnectedClientEntry
from mapadroid.worker.AbstractWorker import AbstractWorker


class Communicator(AbstractCommunicator):
    UPDATE_INTERVAL = 0.4

    def __init__(self, websocket_client_entry: WebsocketConnectedClientEntry, worker_id: str,
                 worker_instance_ref: Optional[AbstractWorker],
                 command_timeout: float):
        # Throws ValueError if unable to connect!
        # catch in code using this class
        self.worker_id: str = worker_id
        self.worker_instance_ref: Optional[AbstractWorker] = worker_instance_ref
        self.websocket_client_entry = websocket_client_entry
        self.__command_timeout: float = command_timeout
        self.__sendMutex = Lock()

    def cleanup(self) -> None:
        logger.info(
            "Communicator of {} calling exit to cleanup worker in websocket", str(self.worker_id))
        try:
            self.terminate_connection()
        except (WebsocketWorkerConnectionClosedException, WebsocketWorkerTimeoutException):
            logger.info("Communicator-cleanup of {} resulted in timeout or connection has already been closed", str(self.worker_id))

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

    def start_app(self, package_name: str) -> bool:
        return self.__runAndOk("more start {}\r\n".format(package_name), self.__command_timeout)

    def stop_app(self, package_name: str) -> bool:
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

    def restart_app(self, package_name: str) -> bool:
        return self.__runAndOk("more restart {}\r\n".format(package_name), self.__command_timeout)

    def reset_app_data(self, package_name: str) -> bool:
        return self.__runAndOk("more reset {}\r\n".format(package_name), self.__command_timeout)

    def clear_app_cache(self, package_name: str) -> bool:
        return self.__runAndOk("more cache {}\r\n".format(package_name), self.__command_timeout)

    def magisk_off(self) -> None:
        self.passthrough("su -c magiskhide --disable")

    def magisk_on(self) -> None:
        self.passthrough("su -c magiskhide --enable")

    def turn_screen_on(self) -> bool:
        return self.__runAndOk("more screen on\r\n", self.__command_timeout)

    def click(self, x: int, y: int) -> bool:
        return self.__runAndOk("screen click {} {}\r\n".format(str(int(round(x))), str(int(round(y)))),
                               self.__command_timeout)

    def swipe(self, x1: int, y1: int, x2: int, y2: int) -> Optional[MessageTyping]:
        return self.__run_get_gesponse("touch swipe {} {} {} {}\r\n".format(
                str(int(round(x1))), str(int(round(y1))), str(int(round(x2))), str(int(round(y2))))
        )

    def touch_and_hold(self, x1: int, y1: int, x2: int, y2: int, duration: int = 3000) -> bool:
        return self.__runAndOk("touch swipe {} {} {} {} {}".format(
            str(int(round(x1))), str(int(round(y1))), str(int(round(x2))), str(int(round(y2))),
            str(int(duration)))
            , self.__command_timeout)

    def get_screensize(self) -> Optional[MessageTyping]:
        return self.__run_get_gesponse("screen size")

    def uiautomator(self) -> Optional[MessageTyping]:
        return self.__run_get_gesponse("more uiautomator")

    def get_screenshot(self, path: str, quality: int = 70,
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

    def back_button(self) -> bool:
        return self.__runAndOk("screen back\r\n", self.__command_timeout)

    def home_button(self) -> bool:
        return self.__runAndOk("touch keyevent 3", self.__command_timeout)

    def enter_button(self) -> bool:
        return self.__runAndOk("touch keyevent 61", self.__command_timeout)

    def enter_text(self, text: str) -> bool:
        return self.__runAndOk("touch text " + str(text), self.__command_timeout)

    def is_screen_on(self) -> bool:
        state = self.__run_get_gesponse("more state screen\r\n")
        if state is None:
            return False
        return "on" in state

    def is_pogo_topmost(self) -> bool:
        topmost = self.__run_get_gesponse("more topmost app\r\n")
        if topmost is None:
            return False
        return "com.nianticlabs.pokemongo" in topmost

    def topmost_app(self) -> Optional[MessageTyping]:
        return self.__run_get_gesponse("more topmost app\r\n")

    def set_location(self, location: Location, altitude: float) -> Optional[MessageTyping]:
        return self.__run_get_gesponse("geo fix {} {} {}\r\n".format(location.lat, location.lng, altitude))

    def terminate_connection(self) -> bool:
        try:
            return self.__runAndOk("exit\r\n", timeout=5)
        except WebsocketWorkerConnectionClosedException:
            logger.info("Cannot gracefully terminate connection of {}, it's already been closed", self.worker_id)
            return True

    # coords need to be float values
    # speed integer with km/h
    #######
    # This blocks!
    #######
    def walk_from_to(self, location_from: Location, location_to: Location, speed: float) -> Optional[MessageTyping]:
        # calculate the time it will take to walk and add it to the timeout!
        distance = get_distance_of_two_points_in_meters(
            location_from.lat, location_from.lng,
            location_to.lat, location_to.lng)
        # speed is in kmph, distance in m
        # we want m/s -> speed / 3.6
        speed_meters = speed / 3.6
        seconds_traveltime = distance / speed_meters
        return self.__run_get_gesponse("geo walk {} {} {} {} {}\r\n".format(location_from.lat, location_from.lng,
                                                                            location_to.lat, location_to.lng,
                                                                            speed),
                                       self.__command_timeout + seconds_traveltime)
