from typing import Dict, Optional

import aiohttp_jinja2
from aiohttp import web
from aiohttp.abc import Request
from aiohttp_jinja2.helpers import url_for

from mapadroid.db.helper.SettingsAuthHelper import SettingsAuthHelper
from mapadroid.db.helper.SettingsMonivlistHelper import SettingsMonivlistHelper
from mapadroid.db.model import SettingsAuth
from mapadroid.db.resource_definitions.Auth import Auth
from mapadroid.madmin.AbstractRootEndpoint import AbstractRootEndpoint


class SettingsAuthEndpoint(AbstractRootEndpoint):
    """
    "/settings/auth"
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
    @aiohttp_jinja2.template('settings_singleauth.html')
    async def _render_single_element(self):
        # Parse the mode to send the correct settings-resource definition accordingly
        auth: Optional[SettingsAuth] = None
        if self.identifier == "new":
            pass
        else:
            auth: SettingsAuth = await SettingsAuthHelper.get(self._session, self._get_instance_id(), int(self.identifier))
            if not auth:
                raise web.HTTPFound(self._url_for("settings_auth"))

        settings_vars: Optional[Dict] = self._get_settings_vars()

        template_data: Dict = {
            'identifier': self.identifier,
            'base_uri': self._url_for('api_auth'),
            'redirect': self._url_for('settings_auth'),
            'subtab': 'auth',
            'element': auth,
            'section': auth,
            'settings_vars': settings_vars,
            'method': 'POST' if not auth else 'PATCH',
            'uri': self._url_for('api_auth') if not auth else '%s/%s' % (self._url_for('api_auth'), self.identifier),
        }
        return template_data

    @aiohttp_jinja2.template('settings_auth.html')
    async def _render_overview(self):
        template_data: Dict = {
            'base_uri': self._url_for('api_auth'),
            'monlist': await SettingsMonivlistHelper.get_entries_mapped(self._session, self._get_instance_id()),
            'subtab': 'auth',
            'section': await SettingsAuthHelper.get_all_mapped(self._session, self._get_instance_id()),
            'redirect': self._url_for('settings_auth'),
        }
        return template_data

    def _get_settings_vars(self) -> Optional[Dict]:
        return Auth.configuration
