from abc import ABC, abstractmethod
from typing import Optional

from mapadroid.utils.CustomTypes import MessageTyping
from mapadroid.utils.collections import Location
from mapadroid.utils.madGlobals import ScreenshotType


class AbstractCommunicator(ABC):
    @abstractmethod
    async def cleanup(self) -> None:
        """
        Cleanup connection
        :return:
        """
        pass

    @abstractmethod
    async def install_apk(self, timeout: float, filepath: str = None, data=None) -> bool:
        pass

    @abstractmethod
    async def install_bundle(self, timeout: float, filepath: str = None, data=None) -> bool:
        pass

    @abstractmethod
    async def start_app(self, package_name: str) -> bool:
        pass

    @abstractmethod
    async def stop_app(self, package_name: str) -> bool:
        pass

    @abstractmethod
    async def passthrough(self, command) -> Optional[MessageTyping]:
        pass

    @abstractmethod
    async def reboot(self) -> bool:
        pass

    @abstractmethod
    async def restart_app(self, package_name: str) -> bool:
        pass

    @abstractmethod
    async def reset_app_data(self, package_name: str) -> bool:
        pass

    @abstractmethod
    async def clear_app_cache(self, package_name: str) -> bool:
        pass

    @abstractmethod
    async def magisk_off(self) -> None:
        pass

    @abstractmethod
    async def magisk_on(self) -> None:
        pass

    @abstractmethod
    async def turn_screen_on(self) -> bool:
        pass

    @abstractmethod
    async def click(self, click_x: int, click_y: int) -> bool:
        pass

    @abstractmethod
    async def swipe(self, x1: int, y1: int, x2: int, y2: int) -> Optional[MessageTyping]:
        pass

    @abstractmethod
    async def touch_and_hold(self, x1: int, y1: int, x2: int, y2: int, duration: int = 3000) -> bool:
        """

        :param x1: From x
        :param y1: From y
        :param x2: To x
        :param y2: To y
        :param duration: in ms
        :return: success indicator
        """
        pass

    @abstractmethod
    async def get_screensize(self) -> Optional[MessageTyping]:
        pass

    @abstractmethod
    async def uiautomator(self) -> Optional[MessageTyping]:
        """
        :return: Output of `uiautomator` shipped with android (or is it busybox?)
        """
        pass

    @abstractmethod
    async def get_screenshot(self, path: str, quality: int = 70,
                             screenshot_type: ScreenshotType = ScreenshotType.JPEG) -> bool:
        """

        :param path: the screenshot is to be stored at
        :param quality: of the screenshot (compression)
        :param screenshot_type: whether it's jpeg or png
        :return: boolean indicating success or failure
        """
        pass

    @abstractmethod
    async def back_button(self) -> bool:
        pass

    @abstractmethod
    async def home_button(self) -> bool:
        """
        Keyevent 3
        :return:
        """
        pass

    @abstractmethod
    async def enter_text(self, text: str) -> bool:
        pass

    @abstractmethod
    async def is_screen_on(self) -> bool:
        """
        Determine whether the screen is turned on
        :return:
        """
        pass

    @abstractmethod
    async def is_pogo_topmost(self) -> bool:
        pass

    @abstractmethod
    async def topmost_app(self) -> Optional[MessageTyping]:
        """
        Return the app / activity that is currently shown
        :return:
        """
        pass

    @abstractmethod
    async def set_location(self, location: Location, altitude: float) -> Optional[MessageTyping]:
        pass

    @abstractmethod
    async def terminate_connection(self) -> bool:
        """
        Gracefully terminate the connection (tell the partner to close)
        :return:
        """

    @abstractmethod
    async def walk_from_to(self, location_from: Location, location_to: Location, speed: float) -> Optional[
        MessageTyping]:
        """

        :param location_from:
        :param location_to:
        :param speed: in km/h
        :return:
        """
        pass

    @abstractmethod
    async def get_compressed_logcat(self, path: str) -> bool:
        """

        Args:
            path: The path to store the compressed logcat at (will be a zip file)

        Returns:

        """
