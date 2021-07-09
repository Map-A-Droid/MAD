from typing import Dict, Optional

from aiohttp.abc import Request

from mapadroid.db.helper import SettingsRoutecalcHelper
from mapadroid.db.model import SettingsArea, SettingsRoutecalc
from mapadroid.madmin.AbstractMadminRootEndpoint import AbstractMadminRootEndpoint


class RecalcStatusEndpoint(AbstractMadminRootEndpoint):
    """
    "/recalc_status"
    """

    def __init__(self, request: Request):
        super().__init__(request)

    # TODO: Auth
    async def get(self):
        recalc = []
        areas: Dict[int, SettingsArea] = await self._get_db_wrapper().get_all_areas(self._session)
        routecalcs: Dict[int, SettingsRoutecalc] = await SettingsRoutecalcHelper.get_all(self._session,
                                                                                         self._get_instance_id())
        for area_id, area in areas.items():
            # TODO: Fetch recalcs...
            routecalc_id: Optional[int] = getattr(area, "routecalc", None)
            if routecalc_id and routecalc_id in routecalcs and routecalcs[routecalc_id].recalc_status == 1:
                recalc.append(area_id)
        return await self._json_response(recalc)
