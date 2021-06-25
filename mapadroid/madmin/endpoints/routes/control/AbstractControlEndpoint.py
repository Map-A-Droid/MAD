import asyncio
import datetime
import os
from abc import ABC
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from aiohttp.abc import Request
from PIL import Image

import mapadroid
from mapadroid.madmin.AbstractMadminRootEndpoint import AbstractMadminRootEndpoint
from mapadroid.madmin.functions import generate_device_screenshot_path
from mapadroid.mapping_manager.MappingManager import DeviceMappingsEntry
from mapadroid.mapping_manager.MappingManagerDevicemappingKey import MappingManagerDevicemappingKey
from mapadroid.utils.adb import ADBConnect
from mapadroid.utils.functions import creation_date, image_resize
from mapadroid.utils.madGlobals import ScreenshotType
from loguru import logger


class AbstractControlEndpoint(AbstractMadminRootEndpoint, ABC):
    """
    Used for control-related endpoints e.g. screenshot handling of devicecontrol
    """

    def __init__(self, request: Request):
        super().__init__(request)
        # TODO: ADB-Connect should be instantiated and passed using the aiohttp-server dict...
        self._adb_connect = ADBConnect(self._get_mad_args())

    async def _take_screenshot(self):
        origin: Optional[str] = self.request.query.get("origin")
        useadb_raw: Optional[str] = self.request.query.get("adb")
        useadb: bool = True if useadb_raw is not None else False

        # TODO: Logger with contextualize
        # origin_logger = get_origin_logger(self._logger, origin=origin)
        # origin_logger.info('MADmin: Making screenshot')

        devicemapping: Optional[DeviceMappingsEntry] = await self._get_mapping_manager().get_devicemappings_of(origin)
        filename = generate_device_screenshot_path(origin, devicemapping, self._get_mad_args())

        if useadb and self._adb_connect.make_screenshot(devicemapping.device_settings.adbname, origin, "jpg"):
            # origin_logger.info('MADmin: ADB screenshot successfully')
            pass
        else:
            await self._generate_screenshot(devicemapping)
        logger.info("Done taking screenshot")
        return datetime.datetime.fromtimestamp(
            creation_date(filename)).strftime(self._datetimeformat)

    async def _generate_screenshot(self, mapping_entry: DeviceMappingsEntry):
        temp_comm = self._get_ws_server().get_origin_communicator(mapping_entry.device_settings.name)
        if not temp_comm:
            logger.warning("Unable to fetch screenshot of a device that is not connected")
            return
        screenshot_type: ScreenshotType = await self._get_mapping_manager()\
            .get_devicesetting_value_of_device(mapping_entry.device_settings.name,
                                               MappingManagerDevicemappingKey.SCREENSHOT_TYPE)
        screenshot_quality: int = await self._get_mapping_manager()\
            .get_devicesetting_value_of_device(mapping_entry.device_settings.name,
                                               MappingManagerDevicemappingKey.SCREENSHOT_QUALITY)
        filename = generate_device_screenshot_path(mapping_entry.device_settings.name, mapping_entry,
                                                   self._get_mad_args())

        await temp_comm.get_screenshot(filename, screenshot_quality, screenshot_type)
        logger.info("Done grabbing screenshot, resizing")
        await image_resize(filename, os.path.join(mapadroid.MAD_ROOT, self._get_mad_args().temp_path, "madmin"),
                           width=250)
        logger.info("Done resizing screenshot")

    def _process_read_screenshot_size(self, filename):
        with Image.open(filename) as screenshot:
            width, height = screenshot.size
        return height, width

    async def _read_screenshot_size(self, filename):
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor() as pool:
            height, width = await loop.run_in_executor(
                pool, self._process_read_screenshot_size, filename)
        return height, width
