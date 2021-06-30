import asyncio
from typing import Optional

from aiohttp import web
from loguru import logger

from mapadroid.madmin.endpoints.routes.control.AbstractControlEndpoint import \
    AbstractControlEndpoint
from mapadroid.mapping_manager.MappingManager import DeviceMappingsEntry


class SendTextEndpoint(AbstractControlEndpoint):
    """
    "/send_text"
    """

    # TODO: Auth
    async def get(self):
        origin: Optional[str] = self.request.query.get("origin")
        text: Optional[str] = self.request.query.get("text")
        devicemapping: Optional[DeviceMappingsEntry] = await self._get_mapping_manager().get_devicemappings_of(origin)
        if not devicemapping:
            logger.warning("Device {} not found.", origin)
            return web.Response(text="Failed clearing game data.")
        # origin_logger = get_origin_logger(self._logger, origin=origin)
        useadb_raw: Optional[str] = self.request.query.get("adb")
        useadb: bool = True if useadb_raw is not None else False

        if len(text) == 0:
            return 'Empty text'
        # origin_logger.info('MADmin: Send text')
        if useadb == 'True' and await self._adb_connect.send_shell_command(devicemapping.device_settings.adbname,
                                                                           origin, 'input text "' + text + '"'):
            # origin_logger.info('MADmin: Send text successfully')
            pass
        else:
            temp_comm = self._get_ws_server().get_origin_communicator(origin)
            await temp_comm.enter_text(text)

        await asyncio.sleep(2)
        creationdate = await self._take_screenshot()
        return web.Response(text=creationdate)
