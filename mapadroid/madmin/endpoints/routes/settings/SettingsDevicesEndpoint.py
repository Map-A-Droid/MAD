from typing import Dict, Optional

import aiohttp_jinja2
from aiohttp import web
from aiohttp.abc import Request

from mapadroid.db.helper.SettingsDeviceHelper import SettingsDeviceHelper
from mapadroid.db.helper.SettingsDevicepoolHelper import SettingsDevicepoolHelper
from mapadroid.db.helper.SettingsPogoauthHelper import SettingsPogoauthHelper, LoginType
from mapadroid.db.helper.SettingsWalkerHelper import SettingsWalkerHelper
from mapadroid.db.model import SettingsDevice
from mapadroid.db.resource_definitions.Device import Device
from mapadroid.madmin.AbstractRootEndpoint import AbstractRootEndpoint


class SettingsDevicesEndpoint(AbstractRootEndpoint):
    """
    "/settings/devices"
    """

    def __init__(self, request: Request):
        super().__init__(request)

    # TODO: Auth
    async def get(self):
        self.identifier: Optional[str] = self.request.query.get("id")
        if self.identifier:
            return await self._render_single_element()
        else:
            return await self._render_overview()

    # TODO: Verify working
    @aiohttp_jinja2.template('settings_singledevice.html')
    async def _render_single_element(self):
        # Parse the mode to send the correct settings-resource definition accordingly
        device: Optional[SettingsDevice] = None
        if self.identifier == "new":
            pass
        else:
            device: SettingsDevice = await SettingsDeviceHelper.get(self._session, self._get_instance_id(),
                                                                    int(self.identifier))
            if not device:
                raise web.HTTPFound(self._url_for("settings_devices"))

        settings_vars: Optional[Dict] = self._get_settings_vars()

        template_data: Dict = {
            'identifier': self.identifier,
            'base_uri': self._url_for('api_device'),
            'redirect': self._url_for('settings_devices'),
            'subtab': 'device',
            'element': device,
            'section': device,
            'settings_vars': settings_vars,
            'method': 'POST' if not device else 'PATCH',
            'uri': self._url_for('api_device') if not device else '%s/%s' % (self._url_for('api_device'), self.identifier),
            # TODO: Above is pretty generic in theory...
            'ggl_accounts': await SettingsPogoauthHelper.get_avail_accounts(self._session, self._get_instance_id(),
                                                                            LoginType.GOOGLE),
            'ptc_accounts': await SettingsPogoauthHelper.get_avail_accounts(self._session, self._get_instance_id(),
                                                                            LoginType.PTC),
            'requires_auth': not self._get_mad_args().autoconfig_no_auth,
            'responsive': str(self._get_mad_args().madmin_noresponsive).lower(),
            'walkers': await SettingsWalkerHelper.get_all_mapped(self._session, self._get_instance_id()),
            'pools': await SettingsDevicepoolHelper.get_all_mapped(self._session, self._get_instance_id()),
        }
        return template_data

    @aiohttp_jinja2.template('settings_devices.html')
    async def _render_overview(self):
        template_data: Dict = {
            'base_uri': self._url_for('api_device'),
            'redirect': self._url_for('settings_devices'),
            'subtab': 'device',
            'section': await SettingsDeviceHelper.get_all_mapped(self._session, self._get_instance_id()),
            'walkers': await SettingsWalkerHelper.get_all_mapped(self._session, self._get_instance_id()),
            'pools': await SettingsDevicepoolHelper.get_all_mapped(self._session, self._get_instance_id()),
        }
        return template_data

    def _get_settings_vars(self) -> Optional[Dict]:
        return Device.configuration
