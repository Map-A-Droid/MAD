from typing import Optional

import aiohttp_jinja2

from mapadroid.madmin.AbstractMadminRootEndpoint import AbstractMadminRootEndpoint, expand_context
from mapadroid.madmin.functions import get_quest_areas


class QuestsEndpoint(AbstractMadminRootEndpoint):
    """
    "/quests"
    """

    # TODO: Auth
    @aiohttp_jinja2.template('quests.html')
    @expand_context()
    async def get(self):
        fence: Optional[str] = self._request.query.get("fence")
        stop_fences = await get_quest_areas(self._get_mapping_manager(), self._session, self._get_instance_id())

        return {
            "pub": False,
            "title": "Show daily quests",
            "time": self._get_mad_args().madmin_time,
            "responsive": str(self._get_mad_args().madmin_noresponsive).lower(),
            "fence": fence,
            "stop_fences": stop_fences
        }
