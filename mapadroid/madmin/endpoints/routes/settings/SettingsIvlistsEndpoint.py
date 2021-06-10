import os
from typing import Dict, Optional, List

import aiohttp_jinja2
from aiohttp import web
from aiohttp.abc import Request
from aiohttp_jinja2.helpers import url_for

from mapadroid.db.helper.SettingsMonivlistHelper import SettingsMonivlistHelper
from mapadroid.db.model import SettingsMonivlist
from mapadroid.db.resource_definitions.MonIvList import MonIvList
from mapadroid.madmin.AbstractRootEndpoint import AbstractRootEndpoint
from mapadroid.utils.language import i8ln, open_json_file


class SettingsIvlistsEndpoint(AbstractRootEndpoint):
    """
    "/settings/monivlists"
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
    @aiohttp_jinja2.template('settings_singleivlist.html')
    async def _render_single_element(self, identifier: str):
        # Parse the mode to send the correct settings-resource definition accordingly
        monivlist: Optional[SettingsMonivlist] = None
        if identifier == "new":
            pass
        else:
            monivlist: SettingsMonivlist = await SettingsMonivlistHelper.get_entry(self._session,
                                                                                   self._get_instance_id(),
                                                                                   int(identifier))
            if not monivlist:
                raise web.HTTPFound(self._url_for("settings_ivlists"))

        settings_vars: Optional[Dict] = self._get_settings_vars()

        try:
            current_mons: Optional[List[int]] = await SettingsMonivlistHelper.get_list(self._session,
                                                                                       self._get_instance_id(),
                                                                                       int(identifier))
        except Exception:
            current_mons = []
        all_pokemon = await self.get_pokemon()
        mondata = all_pokemon['mondata']
        current_mons_list = []
        for mon_id in current_mons:
            try:
                mon_name = await i8ln(mondata[str(mon_id)]["name"])
            except KeyError:
                mon_name = "No-name-in-file-please-fix"
            current_mons_list.append({"mon_name": mon_name, "mon_id": str(mon_id)})

        template_data: Dict = {
            'identifier': identifier,
            'base_uri': self._url_for('api_monivlist'),
            'redirect': self._url_for('settings_ivlists'),
            'subtab': 'monivlist',
            'element': monivlist,
            'section': monivlist,
            'settings_vars': settings_vars,
            'method': 'POST' if not monivlist else 'PATCH',
            'uri': self._url_for('api_monivlist') if not monivlist else '%s/%s' % (self._url_for('api_monivlist'), identifier),
            # TODO: Above is pretty generic in theory...
            'current_mons_list': current_mons_list
        }
        return template_data

    @aiohttp_jinja2.template('settings_ivlists.html')
    async def _render_overview(self):
        template_data: Dict = {
            'base_uri': self._url_for('api_monivlist'),
            'redirect': self._url_for('settings_ivlists'),
            'subtab': 'monivlist',
            'section': await SettingsMonivlistHelper.get_entries_mapped(self._session, self._get_instance_id()),
        }
        return template_data

    def _get_settings_vars(self) -> Optional[Dict]:
        return MonIvList.configuration

    async def get_pokemon(self):
        mondata = await open_json_file('pokemon')
        # Why o.O
        stripped_mondata = {}
        for mon_id in mondata:
            stripped_mondata[mondata[str(mon_id)]["name"]] = mon_id
            if os.environ['LANGUAGE'] != "en":
                try:
                    localized_name = await i8ln(mondata[str(mon_id)]["name"])
                    stripped_mondata[localized_name] = mon_id
                except KeyError:
                    pass
        return {
            'mondata': mondata,
            'locale': stripped_mondata
        }
