from typing import Dict, Optional, List

import aiohttp_jinja2
from aiohttp import web
from aiohttp.abc import Request

from mapadroid.db.helper.SettingsWalkerHelper import SettingsWalkerHelper
from mapadroid.db.helper.SettingsWalkerareaHelper import SettingsWalkerareaHelper
from mapadroid.db.model import SettingsWalker, SettingsWalkerarea, SettingsArea
from mapadroid.db.resource_definitions.Walker import Walker
from mapadroid.madmin.AbstractMadminRootEndpoint import AbstractMadminRootEndpoint


class SettingsWalkerEndpoint(AbstractMadminRootEndpoint):
    """
    "/settings/walker"
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

    # TODO: Verify working
    @aiohttp_jinja2.template('settings_singlewalker.html')
    async def _render_single_element(self):
        # Parse the mode to send the correct settings-resource definition accordingly
        walker: Optional[SettingsWalker] = None
        walkerareas: List[SettingsWalkerarea] = []
        if self._identifier == "new":
            pass
        else:
            walker: SettingsWalker = await SettingsWalkerHelper.get(self._session, self._get_instance_id(),
                                                                    int(self._identifier))
            if not walker:
                raise web.HTTPFound(self._url_for("settings_walkers"))
            walkerareas_mapped: Optional[List[SettingsWalkerarea]] = await SettingsWalkerareaHelper \
                .get_mapped_to_walker(self._session, self._get_instance_id(), walker.walker_id)
            if walkerareas_mapped:
                walkerareas.extend(walkerareas_mapped)
        areas: Dict[int, SettingsArea] = await self._get_db_wrapper().get_all_areas(self._session)

        settings_vars: Optional[Dict] = self._get_settings_vars()
        template_data: Dict = {
            'identifier': self._identifier,
            'base_uri': self._url_for('api_walker'),
            'redirect': self._url_for('settings_walkers'),
            'subtab': 'walker',
            'element': walker,
            'settings_vars': settings_vars,
            'method': 'POST' if not walker else 'PATCH',
            'uri': self._url_for('api_walker') if not walker else '%s/%s' % (
                self._url_for('api_walker'), self._identifier),
            # TODO: Above is pretty generic in theory...
            'walkerareas': walkerareas,
            "areas": areas
        }
        return template_data

    @aiohttp_jinja2.template('settings_walkers.html')
    async def _render_overview(self):
        walkers: Dict[int, SettingsWalker] = await SettingsWalkerHelper.get_all_mapped(self._session,
                                                                                       self._get_instance_id())
        walker_to_walkerares: Dict[int, List[SettingsWalkerarea]] = await SettingsWalkerareaHelper \
            .get_all_mapped_by_walker(self._session, self._get_instance_id())
        areas: Dict[int, SettingsArea] = await self._get_db_wrapper().get_all_areas(self._session)
        template_data: Dict = {
            'base_uri': self._url_for('api_walker'),
            'redirect': self._url_for('settings_walkers'),
            'subtab': 'walker',
            "walker_to_walkerares": walker_to_walkerares,
            'section': walkers,
            "areas": areas
        }
        return template_data

    def _get_settings_vars(self) -> Optional[Dict]:
        return Walker.configuration
