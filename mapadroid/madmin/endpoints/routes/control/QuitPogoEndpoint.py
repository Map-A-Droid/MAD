import asyncio
from typing import Optional

from aiohttp import web
from loguru import logger

from mapadroid.db.helper.TrsStatusHelper import TrsStatusHelper
from mapadroid.madmin.endpoints.routes.control.AbstractControlEndpoint import \
    AbstractControlEndpoint
from mapadroid.mapping_manager.MappingManager import DeviceMappingsEntry


class QuitPogoEndpoint(AbstractControlEndpoint):
    """
    "/quit_pogo"
    """

    # TODO: Auth
    async def get(self) -> web.Response:
        origin: Optional[str] = self.request.query.get("origin")
        # origin_logger = get_origin_logger(self._logger, origin=origin)
        useadb_raw: Optional[str] = self.request.query.get("adb")
        useadb: bool = True if useadb_raw is not None else False

        restart: Optional[str] = self.request.query.get('restart')
        devicemapping: Optional[DeviceMappingsEntry] = await self._get_mapping_manager().get_devicemappings_of(origin)
        if not devicemapping:
            logger.warning("Device {} not found.", origin)
            return web.Response(text="Failed clearing game data.")
        if devicemapping.device_settings.device_id:
            await TrsStatusHelper.save_last_restart(self._session, self._get_instance_id(),
                                                    devicemapping.device_settings.device_id)
        # origin_logger.info('MADmin: Restart Pogo')
        if useadb and await self._adb_connect.send_shell_command(devicemapping.device_settings.adbname,
                                                           origin, "am force-stop com.nianticlabs.pokemongo"):
            # origin_logger.info('MADmin: ADB shell force-stop game command successfully')
            if restart:
                await asyncio.sleep(1)
                started = await self._adb_connect.send_shell_command(devicemapping.device_settings.adbname,
                                                               origin, "am start com.nianticlabs.pokemongo")
                if started:
                    # origin_logger.info('MADmin: ADB shell start game command successfully')
                    pass
                else:
                    # origin_logger.error('MADmin: ADB shell start game command failed')
                    pass
        else:
            temp_comm = self._get_ws_server().get_origin_communicator(origin)
            if restart:
                # origin_logger.info('MADmin: trying to restart game')
                await temp_comm.restart_app("com.nianticlabs.pokemongo")
                await asyncio.sleep(1)
            else:
                # origin_logger.info('MADmin: trying to stop game')
                await temp_comm.stop_app("com.nianticlabs.pokemongo")

            # origin_logger.info('MADmin: WS command successfully')

        creationdate = await self._take_screenshot()
        return web.Response(text=creationdate)
