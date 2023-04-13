from typing import Optional

import aiohttp_jinja2

from mapadroid.db.model import AuthLevel
from mapadroid.madmin.AbstractMadminRootEndpoint import (
    AbstractMadminRootEndpoint, check_authorization_header, expand_context)
from mapadroid.madmin.functions import get_quest_areas


class QuestsEndpoint(AbstractMadminRootEndpoint):
    """
    "/quests"
    """

    @check_authorization_header(AuthLevel.MADMIN_ADMIN)
    @aiohttp_jinja2.template('quests.html')
    @expand_context()
    async def get(self):
        fence: Optional[str] = self._request.query.get("fence")
        stop_fences = await get_quest_areas(self._get_mapping_manager())

        return {
            "pub": False,
            "title": "Show daily quests",
            "time": self._get_mad_args().madmin_time,
            "responsive": str(self._get_mad_args().madmin_noresponsive).lower(),
            "fence": fence,
            "stop_fences": stop_fences
        }
