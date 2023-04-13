import asyncio
from typing import Optional

from aiohttp import web
from loguru import logger

from mapadroid.madmin.endpoints.routes.control.AbstractControlEndpoint import \
    AbstractControlEndpoint
from mapadroid.mapping_manager.MappingManager import DeviceMappingsEntry


class SendCommandEndpoint(AbstractControlEndpoint):
    """
    "/send_command"
    """

    async def get(self):
        origin: Optional[str] = self.request.query.get("origin")
        devicemapping: Optional[DeviceMappingsEntry] = await self._get_mapping_manager().get_devicemappings_of(origin)
        if not devicemapping:
            logger.warning("Device {} not found.", origin)
            return web.Response(text="Failed clearing game data.")
        # origin_logger = get_origin_logger(self._logger, origin=origin)
        useadb_raw: Optional[str] = self.request.query.get("adb")
        useadb: bool = True if useadb_raw is not None else False
        command = self.request.query.get('command')
        adb_cmd = ""
        if command == 'home':
            adb_cmd = "input keyevent 3"
        elif command == 'back':
            adb_cmd = "input keyevent 4"
        if useadb and await self._adb_connect.send_shell_command(devicemapping.device_settings.adbname, origin,
                                                                 adb_cmd):
            pass
        else:
            temp_comm = self._get_ws_server().get_origin_communicator(origin)
            if command == 'home':
                await temp_comm.home_button()
            elif command == 'back':
                await temp_comm.back_button()

        logger.info('MADmin: Command "{}"', command)
        await asyncio.sleep(2)
        creationdate = await self._take_screenshot()
        return web.Response(text=creationdate)
