from typing import Dict, List, Optional

import aiohttp_jinja2
from aiohttp import web
from aiohttp.abc import Request

from mapadroid.db.helper.SettingsAuthHelper import SettingsAuthHelper
from mapadroid.db.helper.SettingsMonivlistHelper import SettingsMonivlistHelper
from mapadroid.db.model import AuthLevel, SettingsAuth
from mapadroid.db.resource_definitions.Auth import Auth
from mapadroid.madmin.AbstractMadminRootEndpoint import (
    AbstractMadminRootEndpoint, check_authorization_header, expand_context)


class SettingsAuthEndpoint(AbstractMadminRootEndpoint):
    """
    "/settings/auth"
    """

    def __init__(self, request: Request):
        super().__init__(request)

    @check_authorization_header(AuthLevel.MADMIN_ADMIN)
    async def get(self):
        self._identifier: Optional[str] = self.request.query.get("id")
        if self._identifier:
            return await self._render_single_element()
        else:
            return await self._render_overview()

    @aiohttp_jinja2.template('settings_singleauth.html')
    @expand_context()
    async def _render_single_element(self):
        # Parse the mode to send the correct settings-resource definition accordingly
        auth: Optional[SettingsAuth] = None
        if self._identifier == "new":
            pass
        else:
            auth: SettingsAuth = await SettingsAuthHelper.get(self._session, self._get_instance_id(),
                                                              int(self._identifier))
            if not auth:
                raise web.HTTPFound(self._url_for("settings_auth"))
        auth_level_stringified: str = ""
        if auth:
            auth_level_stringified = self._stringify_auth_level(auth)
        settings_vars: Optional[Dict] = self._get_settings_vars()
        template_data: Dict = {
            'identifier': self._identifier,
            'base_uri': self._url_for('api_auth'),
            'redirect': self._url_for('settings_auth'),
            'subtab': 'auth',
            'element': auth,
            'section': auth,
            'auth_levels': AuthLevel,
            'auth_level_set': auth_level_stringified,
            'settings_vars': settings_vars,
            'method': 'POST' if not auth else 'PATCH',
            'uri': self._url_for('api_auth') if not auth else '%s/%s' % (self._url_for('api_auth'), self._identifier),
        }
        return template_data

    def _stringify_auth_level(self, auth: SettingsAuth):
        current_auth_levels: List[str] = []
        for auth_level in AuthLevel:
            if auth.auth_level & auth_level.value:
                current_auth_levels.append(auth_level.name)
        auth_level_stringified = ','.join(current_auth_levels)
        return auth_level_stringified

    @aiohttp_jinja2.template('settings_auth.html')
    @expand_context()
    async def _render_overview(self):
        auths: Dict[int, SettingsAuth] = await SettingsAuthHelper.get_all_mapped(self._session, self._get_instance_id())
        auth_levels_stringified: Dict[int, str] = {}
        for auth_id, auth_entry in auths.items():
            auth_levels_stringified[auth_id] = self._stringify_auth_level(auth_entry)
        template_data: Dict = {
            'base_uri': self._url_for('api_auth'),
            'monlist': await SettingsMonivlistHelper.get_entries_mapped(self._session, self._get_instance_id()),
            'subtab': 'auth',
            'section': auths,
            'auth_levels': auth_levels_stringified,
            'redirect': self._url_for('settings_auth'),
        }
        return template_data

    def _get_settings_vars(self) -> Optional[Dict]:
        return Auth.configuration
