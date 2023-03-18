from typing import Dict, Optional, List, Tuple

import aiohttp_jinja2
import datetime
from aiohttp import web
from aiohttp.abc import Request

from mapadroid.db.helper.SettingsDeviceHelper import SettingsDeviceHelper
from mapadroid.db.helper.SettingsPogoauthHelper import SettingsPogoauthHelper
from mapadroid.db.model import SettingsDevice, SettingsPogoauth
from mapadroid.db.resource_definitions.Pogoauth import Pogoauth
from mapadroid.madmin.AbstractMadminRootEndpoint import AbstractMadminRootEndpoint, expand_context
from mapadroid.utils.DatetimeWrapper import DatetimeWrapper
from mapadroid.utils.global_variables import MAINTENANCE_COOLDOWN_HOURS

class SettingsPogoauthEndpoint(AbstractMadminRootEndpoint):
    """
    "/settings/pogoauth"
    """

    def __init__(self, request: Request):
        super().__init__(request)

    # TODO: Auth
    async def get(self):
        self._identifier: Optional[str] = self.request.query.get("id")
        if self._identifier:
            return await self._render_single_element()
        else:
            return await self._render_overview()

    @aiohttp_jinja2.template('settings_singlepogoauth.html')
    @expand_context()
    async def _render_single_element(self):
        # Parse the mode to send the correct settings-resource definition accordingly
        pogoauth: Optional[SettingsPogoauth] = None
        if self._identifier == "new":
            pass
        else:
            pogoauth: SettingsPogoauth = await SettingsPogoauthHelper.get(self._session,
                                                                          self._get_instance_id(),
                                                                          int(self._identifier))
            if not pogoauth:
                raise web.HTTPFound(self._url_for("settings_pogoauth"))

        settings_vars: Optional[Dict] = self._get_settings_vars()

        devices: List[SettingsDevice] = await SettingsDeviceHelper.get_all(self._session, self._get_instance_id())
        devs_google: List[Tuple[int, str]] = []
        devs_ptc: List[Tuple[int, str]] = []

        available_devices: Dict[int, SettingsDevice] = await SettingsPogoauthHelper.get_available_devices(self._session,
                                                                                                          self._get_instance_id(),
                                                                                                          int(self._identifier) if self._identifier != "new" else None)
        # TODO: Does this make sense?
        for dev_id, dev in available_devices.items():
            devs_google.append((dev_id, dev.name))
        for dev_id, dev in available_devices.items():
            devs_ptc.append((dev_id, dev.name))

        template_data: Dict = {
            'identifier': self._identifier,
            'base_uri': self._url_for('api_pogoauth'),
            'redirect': self._url_for('settings_pogoauth'),
            'subtab': 'pogoauth',
            'element': pogoauth,
            'settings_vars': settings_vars,
            'method': 'POST' if not pogoauth else 'PATCH',
            'uri': self._url_for('api_pogoauth') if not pogoauth else '%s/%s' % (
                self._url_for('api_pogoauth'), self._identifier),
            # TODO: Above is pretty generic in theory...
            'devices': devices,
            'devs_google': devs_google,
            'devs_ptc': devs_ptc
        }
        return template_data

    @aiohttp_jinja2.template('settings_pogoauth.html')
    @expand_context()
    async def _render_overview(self):
        devices: Dict[int, SettingsDevice] = await SettingsDeviceHelper.get_all_mapped(self._session,
                                                                                       self._get_instance_id())
        pogoauth: Dict[int, SettingsPogoauth] = await SettingsPogoauthHelper.get_all_mapped(self._session,
                                                                                            self._get_instance_id())
            
         ban_times_icon = {}
         _now = DatetimeWrapper.now()
         for key in pogoauth:
              if pogoauth[key].last_burn is not None:
                  if pogoauth[key].last_burn + datetime.timedelta(hours=MAINTENANCE_COOLDOWN_HOURS) < DatetimeWrapper.now():
                      ban_times_icon[key] = "fa-exclamation-triangle"
                  else:
                      ban_times_icon[key] = "fa-exclamation-circle"

        template_data: Dict = {
            'base_uri': self._url_for('api_pogoauth'),
            'redirect': self._url_for('settings_pogoauth'),
            'subtab': 'pogoauth',
            'devices': devices,
            'section': pogoauth,
            'ban_times_icon': ban_times_icon,
        }
        return template_data

    def _get_settings_vars(self) -> Optional[Dict]:
        return Pogoauth.configuration
