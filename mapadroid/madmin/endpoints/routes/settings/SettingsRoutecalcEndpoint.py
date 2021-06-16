from typing import Dict, Optional

import aiohttp_jinja2
from aiohttp import web
from aiohttp.abc import Request
from aiohttp_jinja2.helpers import url_for

from mapadroid.db.helper.SettingsRoutecalcHelper import SettingsRoutecalcHelper
from mapadroid.db.model import SettingsMonivlist, SettingsArea, SettingsRoutecalc
from mapadroid.db.resource_definitions.Routecalc import Routecalc
from mapadroid.madmin.AbstractMadminRootEndpoint import AbstractMadminRootEndpoint


class SettingsRoutecalcEndpoint(AbstractMadminRootEndpoint):
    """
    "/settings/routecalc"
    """

    def __init__(self, request: Request):
        super().__init__(request)

    # TODO: Auth
    @aiohttp_jinja2.template('settings_singleroutecalc.html')
    async def get(self):
        self.identifier: Optional[str] = self.request.query.get("id")
        if self.identifier:
            return await self._render_single_element()
        else:
            raise web.HTTPFound(self._url_for("settings_areas"))

    # TODO: Verify working
    @aiohttp_jinja2.template('settings_singleroutecalc.html')
    async def _render_single_element(self):
        # Parse the mode to send the correct settings-resource definition accordingly
        routecalc: Optional[SettingsRoutecalc] = None
        if self.identifier == "new":
            pass
        else:
            routecalc: SettingsRoutecalc = await SettingsRoutecalcHelper.get(self._session,
                                                                             int(self.identifier))
            if not routecalc:
                raise web.HTTPFound(self._url_for("settings_areas"))

        settings_vars: Optional[Dict] = self._get_settings_vars()

        area_id: str = self.request.query.get("area_id")
        if not area_id:
            raise web.HTTPFound(self._url_for("settings_areas"))
        area: Optional[SettingsArea] = await self._get_db_wrapper().get_area(self._session, int(area_id))
        if not area or self.identifier != "new" and getattr(area, "routecalc", None) != int(self.identifier):
            raise web.HTTPFound(self._url_for("settings_areas"))

        template_data: Dict = {
            'identifier': self.identifier,
            'base_uri': self._url_for('api_routecalc'),
            'redirect': self._url_for('settings_areas'),
            'subtab': 'routecalc',
            'element': routecalc,
            'settings_vars': settings_vars,
            'method': 'POST' if not routecalc else 'PATCH',
            'uri': self._url_for('api_routecalc') if not routecalc else '%s/%s' % (self._url_for('api_routecalc'), self.identifier),
            # TODO: Above is pretty generic in theory...
            'area': area,
        }
        return template_data

    def _get_settings_vars(self) -> Optional[Dict]:
        return Routecalc.configuration
