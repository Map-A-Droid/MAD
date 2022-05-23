from typing import Dict, Optional

import aiohttp_jinja2
from aiohttp import web
from aiohttp.abc import Request

from mapadroid.db.helper.SettingsGeofenceHelper import SettingsGeofenceHelper
from mapadroid.db.model import SettingsGeofence
from mapadroid.db.resource_definitions.Geofence import Geofence
from mapadroid.madmin.AbstractMadminRootEndpoint import AbstractMadminRootEndpoint, expand_context


class SettingsGeofenceEndpoint(AbstractMadminRootEndpoint):
    """
    "/settings/geofences"
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

    @aiohttp_jinja2.template('settings_singlegeofence.html')
    @expand_context()
    async def _render_single_element(self):
        # Parse the mode to send the correct settings-resource definition accordingly
        geofence: Optional[SettingsGeofence] = None
        if self._identifier == "new":
            pass
        else:
            geofence: SettingsGeofence = await SettingsGeofenceHelper.get(self._session, self._get_instance_id(),
                                                                          int(self._identifier))
            if not geofence:
                raise web.HTTPFound(self._url_for("settings_geofence"))

        settings_vars: Optional[Dict] = self._get_settings_vars()

        template_data: Dict = {
            'identifier': self._identifier,
            'base_uri': self._url_for('api_geofence'),
            'redirect': self._url_for('settings_geofence'),
            'subtab': 'geofence',
            'element': geofence,
            'section': geofence,
            'settings_vars': settings_vars,
            'method': 'POST' if not geofence else 'PATCH',
            'uri': self._url_for('api_geofence') if not geofence else '%s/%s' % (
                self._url_for('api_geofence'), self._identifier),
            # TODO: Above is pretty generic in theory...
        }
        return template_data

    @aiohttp_jinja2.template('settings_geofences.html')
    @expand_context()
    async def _render_overview(self):
        template_data: Dict = {
            'base_uri': self._url_for('api_geofence'),
            'redirect': self._url_for('settings_geofence'),
            'subtab': 'geofence',
            'section': await SettingsGeofenceHelper.get_all_mapped(self._session, self._get_instance_id()),
        }
        return template_data

    def _get_settings_vars(self) -> Optional[Dict]:
        return Geofence.configuration
