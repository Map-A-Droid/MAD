from typing import Optional

import aiohttp_jinja2

from mapadroid.madmin.AbstractMadminRootEndpoint import expand_context
from mapadroid.madmin.endpoints.routes.statistics.AbstractStatistictsRootEndpoint import AbstractStatisticsRootEndpoint


class SpawnDetailsEndpoint(AbstractStatisticsRootEndpoint):
    """
    "/spawn_details"
    """

    # TODO: Auth
    @aiohttp_jinja2.template('statistics/spawn_details.html')
    @expand_context()
    async def get(self):
        area_id: Optional[int] = self._request.query.get("id")
        if area_id:
            area_id = int(area_id)
        event_id: Optional[int] = self._request.query.get("eventid")
        if event_id:
            event_id = int(event_id)
        # TODO: Check if str
        event: Optional[str] = self._request.query.get("event")
        mode: Optional[str] = self._request.query.get("mode")
        if not mode:
            mode = "OLD"
        index: Optional[int] = self._request.query.get("index")
        if not index:
            index = 0
        else:
            index = int(index)

        return {
            "title": "MAD Statistics",
            "time": self._get_mad_args().madmin_time,
            "responsive": str(self._get_mad_args().madmin_noresponsive).lower(),
            "index": index,
            "older_than_x_days": self.outdatedays,
            "area_id": area_id, "event_id": event_id, "event": event, "mode": mode,

        }
