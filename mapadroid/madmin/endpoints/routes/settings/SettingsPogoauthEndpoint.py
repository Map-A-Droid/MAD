from typing import Dict, Optional, List, Tuple

import aiohttp_jinja2
from aiohttp import web
from aiohttp.abc import Request

from mapadroid.db.helper.SettingsDeviceHelper import SettingsDeviceHelper
from mapadroid.db.helper.SettingsPogoauthHelper import SettingsPogoauthHelper
from mapadroid.db.model import SettingsMonivlist, SettingsDevice, SettingsPogoauth
from mapadroid.db.resource_definitions.Pogoauth import Pogoauth
from mapadroid.madmin.AbstractMadminRootEndpoint import AbstractMadminRootEndpoint


class SettingsPogoauthEndpoint(AbstractMadminRootEndpoint):
    """
    "/settings/pogoauth"
    """

    def __init__(self, request: Request):
        super().__init__(request)

    # TODO: Auth
    async def get(self):
        identifier: Optional[str] = self.request.query.get("id")
        if identifier:
            return await self._render_single_element(identifier=identifier)
        else:
            return await self._render_overview()

    # TODO: Verify working
    @aiohttp_jinja2.template('settings_singlepogoauth.html')
    async def _render_single_element(self, identifier: str):
        # Parse the mode to send the correct settings-resource definition accordingly
        pogoauth: Optional[SettingsMonivlist] = None
        if identifier == "new":
            pass
        else:
            pogoauth: SettingsMonivlist = await SettingsPogoauthHelper.get(self._session,
                                                                           self._get_instance_id(),
                                                                           int(identifier))
            if not pogoauth:
                raise web.HTTPFound(self._url_for("settings_pogoauth"))

        settings_vars: Optional[Dict] = self._get_settings_vars()

        devices: List[SettingsDevice] = await SettingsDeviceHelper.get_all(self._session, self._get_instance_id())
        devs_google: List[Tuple[int, str]] = []
        devs_ptc: List[Tuple[int, str]] = []

        available_devices: Dict[int, SettingsDevice] = await SettingsPogoauthHelper.get_available_devices(self._session,
                                                                                                          self._get_instance_id(),
                                                                                                          int(identifier))
        # TODO: Does this make sense?
        for dev_id, dev in available_devices.items():
            devs_google.append((dev_id, dev.name))
        for dev_id, dev in available_devices.items():
            devs_ptc.append((dev_id, dev.name))

        template_data: Dict = {
            'identifier': identifier,
            'base_uri': self._url_for('api_pogoauth'),
            'redirect': self._url_for('settings_pogoauth'),
            'subtab': 'pogoauth',
            'element': pogoauth,
            'settings_vars': settings_vars,
            'method': 'POST' if not pogoauth else 'PATCH',
            'uri': self._url_for('api_pogoauth') if not pogoauth else '%s/%s' % (
            self._url_for('api_pogoauth'), identifier),
            # TODO: Above is pretty generic in theory...
            'devices': devices,
            'devs_google': devs_google,
            'devs_ptc': devs_ptc
        }
        return template_data

    @aiohttp_jinja2.template('settings_pogoauth.html')
    async def _render_overview(self):
        devices: Dict[int, SettingsDevice] = await SettingsDeviceHelper.get_all_mapped(self._session,
                                                                                       self._get_instance_id())
        pogoauth: Dict[int, SettingsPogoauth] = await SettingsPogoauthHelper.get_all_mapped(self._session,
                                                                                            self._get_instance_id())
        template_data: Dict = {
            'base_uri': self._url_for('api_pogoauth'),
            'redirect': self._url_for('settings_pogoauth'),
            'subtab': 'pogoauth',
            'devices': devices,
            'section': pogoauth,
        }
        return template_data

    def _get_settings_vars(self) -> Optional[Dict]:
        return Pogoauth.configuration
