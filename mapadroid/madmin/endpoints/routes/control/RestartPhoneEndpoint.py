from typing import Optional

from aiohttp import web
from aiohttp_jinja2.helpers import url_for

from mapadroid.db.helper.TrsStatusHelper import TrsStatusHelper
from mapadroid.madmin.endpoints.routes.control.AbstractControlEndpoint import \
    AbstractControlEndpoint
from mapadroid.mapping_manager.MappingManager import DeviceMappingsEntry


class RestartPhoneEndpoint(AbstractControlEndpoint):
    """
    "/restart_phone"
    """

    # TODO: Auth
    async def get(self):
        origin: Optional[str] = self.request.query.get("origin")
        useadb_raw: Optional[str] = self.request.query.get("adb")
        useadb: bool = True if useadb_raw else False
        # origin_logger = get_origin_logger(self._logger, origin=origin)
        devicemapping: Optional[DeviceMappingsEntry] = await self._get_mapping_manager().get_devicemappings_of(origin)
        if not devicemapping:
            raise web.HTTPFound(self._url_for("get_phonescreens"))

        if devicemapping.device_settings.device_id:
            await TrsStatusHelper.save_last_reboot(self._session, self._get_instance_id(),
                                                   devicemapping.device_settings.device_id)
        # origin_logger.info('MADmin: Restart device')
        cmd = "am broadcast -a android.intent.action.BOOT_COMPLETED"
        if useadb and await self._adb_connect.send_shell_command(devicemapping.device_settings.adbname, origin, cmd):
            # origin_logger.info('MADmin: ADB shell command successfully')
            pass
        else:
            temp_comm = self._get_ws_server().get_origin_communicator(origin)
            await temp_comm.reboot()
        await self._get_ws_server().force_disconnect(origin)
        raise web.HTTPFound(self._url_for("get_phonescreens"))
