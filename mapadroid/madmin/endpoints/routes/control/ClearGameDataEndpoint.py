from typing import Optional

from aiohttp import web
from loguru import logger

from mapadroid.madmin.endpoints.routes.control.AbstractControlEndpoint import \
    AbstractControlEndpoint
from mapadroid.mapping_manager.MappingManager import DeviceMappingsEntry


class ClearGameDataEndpoint(AbstractControlEndpoint):
    """
    "/clear_game_data"
    """

    async def get(self):
        origin: Optional[str] = self.request.query.get("origin")
        useadb_raw: Optional[str] = self.request.query.get("adb")
        useadb: bool = True if useadb_raw is not None else False
        # origin_logger = get_origin_logger(self._logger, origin=origin)
        devicemapping: Optional[DeviceMappingsEntry] = await self._get_mapping_manager().get_devicemappings_of(origin)
        if not devicemapping:
            logger.warning("Device {} not found.", origin)
            return web.Response(text="Failed clearing game data.")
        # origin_logger.info('MADmin: Clear game data for device')
        if (useadb and
                await self._adb_connect.send_shell_command(devicemapping.device_settings.adbname, origin,
                                                           "pm clear com.nianticlabs.pokemongo")):
            pass
            # origin_logger.info('MADmin: ADB shell command successfully')
        else:
            temp_comm = self._get_ws_server().get_origin_communicator(origin)
            await temp_comm.reset_app_data("com.nianticlabs.pokemongo")
        raise web.HTTPFound(self._url_for("get_phonescreens"))
