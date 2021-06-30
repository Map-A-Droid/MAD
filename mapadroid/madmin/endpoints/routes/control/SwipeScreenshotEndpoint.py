import asyncio
from typing import Optional

from aiohttp import web
from loguru import logger

from mapadroid.madmin.endpoints.routes.control.AbstractControlEndpoint import \
    AbstractControlEndpoint
from mapadroid.madmin.functions import generate_device_screenshot_path
from mapadroid.mapping_manager.MappingManager import DeviceMappingsEntry


class SwipeScreenshotEndpoint(AbstractControlEndpoint):
    """
    "/swipe_screenshot"
    """

    # TODO: Auth
    async def get(self) -> web.Response:
        origin: Optional[str] = self.request.query.get("origin")
        # origin_logger = get_origin_logger(self._logger, origin=origin)
        click_x: Optional[str] = self.request.query.get("clickx")
        click_y: Optional[str] = self.request.query.get("clicky")
        click_xe: Optional[str] = self.request.query.get('clickxe')
        click_ye: Optional[str] = self.request.query.get('clickye')
        useadb_raw: Optional[str] = self.request.query.get("adb")
        useadb: bool = True if useadb_raw is not None else False
        devicemapping: Optional[DeviceMappingsEntry] = await self._get_mapping_manager().get_devicemappings_of(origin)
        if not devicemapping:
            logger.warning("Device {} not found.", origin)
            return web.Response(text="Failed clearing game data.")

        filename = generate_device_screenshot_path(origin, devicemapping, self._get_mad_args())
        height, width = await self._read_screenshot_size(filename)

        real_click_x = int(width / float(click_x))
        real_click_y = int(height / float(click_y))
        real_click_xe = int(width / float(click_xe))
        real_click_ye = int(height / float(click_ye))
        if useadb and self._adb_connect.make_screenswipe(devicemapping.device_settings.adbname, origin,
                                                         real_click_x, real_click_y, real_click_xe, real_click_ye):
            # origin_logger.info('MADmin: ADB screenswipe successfully')
            pass
        else:
            # origin_logger.info('MADmin WS Swipe x:{} y:{} xe:{} ye:{}', real_click_x, real_click_y, real_click_xe,
            #                   real_click_ye)
            temp_comm = self._get_ws_server().get_origin_communicator(origin)
            await temp_comm.touch_and_hold(int(real_click_x), int(real_click_y), int(real_click_xe), int(real_click_ye))

        await asyncio.sleep(2)
        creationdate = await self._take_screenshot()
        return web.Response(text=creationdate)
