from typing import Optional, Dict, Tuple

from mapadroid.db.helper.AutoconfigRegistrationHelper import AutoconfigRegistrationHelper
from mapadroid.db.helper.SettingsDeviceHelper import SettingsDeviceHelper
from mapadroid.db.model import SettingsDevice, AutoconfigRegistration
from mapadroid.mitm_receiver.endpoints.AbstractDeviceAuthEndpoint import AbstractDeviceAuthEndpoint
from mapadroid.mitm_receiver.endpoints.AbstractMitmReceiverRootEndpoint import AbstractMitmReceiverRootEndpoint
from aiohttp import web


class AutoconfMymacEndpoint(AbstractMitmReceiverRootEndpoint):
    """
    "/autoconfig/mymac"
    """

    async def preprocess(self) -> Tuple[Dict, SettingsDevice]:
        origin = self.request.headers.get('Origin')
        if origin is None:
            raise web.HTTPNotFound
        device: Optional[SettingsDevice] = await SettingsDeviceHelper.get_by_origin(self._session,
                                                                                    self._get_instance_id(),
                                                                                    origin)
        if not device:
            raise web.HTTPNotFound
        autoconf: Optional[AutoconfigRegistration] = await AutoconfigRegistrationHelper.get_of_device(self._session,
                                                                                                      self._get_instance_id(),
                                                                                                      device.device_id)
        log_data: Dict = {}
        if autoconf is not None:
            log_data = {
                'session_id': autoconf.session_id,
                'instance_id': self._get_instance_id(),
                'level': 2
            }
        return log_data, device

    async def get(self):
        log_data, device = await self.preprocess()
        if log_data:
            log_data['msg'] = 'Getting assigned MAC device'
            await self.autoconfig_log(**log_data)
        try:
            mac_type = device.interface_type if device.interface_type else 'lan'
            mac_addr = device.mac_address
            if mac_addr is None:
                mac_addr = ''
            if log_data:
                log_data['msg'] = "Assigned MAC Address: '{}'".format(mac_addr)
                await self.autoconfig_log(**log_data)
            return web.Response(status=200, text='\n'.join([mac_type, mac_addr]))
        except KeyError:
            if log_data:
                log_data['msg'] = 'No assigned MAC address.  Device will generate a new one'
                await self.autoconfig_log(**log_data)
            return web.Response(status=200, text="")

    # TODO: Auth/preprocessing for autoconfig?
    async def post(self):
        log_data, device = await self.preprocess()
        data = str(await self.request.read(), 'utf-8')
        if log_data:
            log_data['msg'] = 'Device is requesting a new MAC address be set, {}'.format(data)
            await self.autoconfig_log(**log_data)
        if not data:
            if log_data:
                log_data['msg'] = 'No MAC provided during MAC assignment'
                await self.autoconfig_log(**log_data)
            return web.Response(status=400, text='No MAC provided')
        try:
            device.mac_address = data
            self._save(device)
            return web.Response(text="", status=200)
        except Exception:
            return web.Response(text="", status=422)
