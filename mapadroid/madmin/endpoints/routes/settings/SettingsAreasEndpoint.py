from typing import Dict, Optional

import aiohttp_jinja2
from aiohttp import web
from aiohttp.abc import Request
from loguru import logger

from mapadroid.db.helper.SettingsGeofenceHelper import SettingsGeofenceHelper
from mapadroid.db.helper.SettingsMonivlistHelper import SettingsMonivlistHelper
from mapadroid.db.model import SettingsArea
from mapadroid.db.resource_definitions.AreaIdle import AreaIdle
from mapadroid.db.resource_definitions.AreaIvMitm import AreaIvMitm
from mapadroid.db.resource_definitions.AreaMonMitm import AreaMonMitm
from mapadroid.db.resource_definitions.AreaPokestops import AreaPokestops
from mapadroid.db.resource_definitions.AreaRaidsMitm import AreaRaidsMitm
from mapadroid.madmin.AbstractMadminRootEndpoint import AbstractMadminRootEndpoint
from mapadroid.worker.WorkerType import WorkerType


class SettingsAreasEndpoint(AbstractMadminRootEndpoint):
    """
    "/settings/areas"
    """

    def __init__(self, request: Request):
        super().__init__(request)
        # check if we can use ortools and if it's installed
        self._ortools_info = False
        try:
            from ortools.constraint_solver import pywrapcp, routing_enums_pb2
        except Exception:
            pass
        import platform

        if platform.architecture()[0] == "64bit":
            try:
                pywrapcp
                routing_enums_pb2
            except Exception:
                self._ortools_info = True

    # TODO: Auth
    async def get(self):
        self._identifier: Optional[str] = self.request.query.get("id")
        if self._identifier:
            return await self._render_single_area()
        else:
            return await self._render_area_overview()

    # TODO: Verify working
    @aiohttp_jinja2.template('settings_singlearea.html')
    async def _render_single_area(self):
        # Parse the mode to send the correct settings-resource definition accordingly
        mode: WorkerType = WorkerType.MON_MITM
        area: Optional[SettingsArea] = None
        if self._identifier == "new":
            mode_raw: Optional[str] = self.request.query.get("mode")
            mode = WorkerType(mode_raw)
        else:
            area: SettingsArea = await self._get_db_wrapper().get_area(self._session, int(self._identifier))
            if not area:
                raise web.HTTPFound(self._url_for("settings_areas"))
            mode = WorkerType(area.mode)

        settings_vars: Optional[Dict] = self._get_settings_vars(mode)
        if not settings_vars:
            logger.warning("Unable to get resource definition for mode {}", mode)
            raise web.HTTPFound(self._url_for("settings_areas"))

        template_data: Dict = {
            'base_uri': self._url_for('api_area'),
            'identifier': self._identifier,
            'monlist': await SettingsMonivlistHelper.get_entries_mapped(self._session, self._get_instance_id()),
            'fences': await SettingsGeofenceHelper.get_all_mapped(self._session, self._get_instance_id()),
            'config_mode': self._get_mad_args().config_mode,
            'ortools_info': self._ortools_info,
            'settings_vars': settings_vars,
            'method': 'POST' if not area else 'PATCH',
            'subtab': 'area',
            'element': area,
            'redirect': self._url_for('settings_areas'),
            'uri': self._url_for('api_area', query={"mode": mode.value}) if not area else '%s/%s' % (
                self._url_for('api_area'), self._identifier),
            'section': area
        }
        return template_data

    @aiohttp_jinja2.template('settings_areas.html')
    async def _render_area_overview(self):
        # TODO: Pass list of boolean settings of all config types?
        all_areas: Dict[int, SettingsArea] = await self._get_db_wrapper().get_all_areas(self._session)
        template_data: Dict = {
            'base_uri': self._url_for('api_area'),
            'monlist': await SettingsMonivlistHelper.get_entries_mapped(self._session, self._get_instance_id()),
            'fences': await SettingsGeofenceHelper.get_all_mapped(self._session, self._get_instance_id()),
            'config_mode': self._get_mad_args().config_mode,
            'ortools_info': self._ortools_info,
            'subtab': 'area',
            'section': all_areas
        }
        return template_data

    def _get_settings_vars(self, mode: WorkerType) -> Optional[Dict]:
        if mode == WorkerType.IDLE:
            return AreaIdle.configuration
        elif mode == WorkerType.IV_MITM:
            return AreaIvMitm.configuration
        elif mode == WorkerType.MON_MITM:
            return AreaMonMitm.configuration
        elif mode == WorkerType.STOPS:
            return AreaPokestops.configuration
        elif mode == WorkerType.RAID_MITM:
            return AreaRaidsMitm.configuration
        else:
            return None
