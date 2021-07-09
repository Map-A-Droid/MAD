from typing import Optional

from mapadroid.madmin.endpoints.routes.statistics.AbstractStatistictsRootEndpoint import AbstractStatisticsRootEndpoint


class GetSpawnDetailsEndpoint(AbstractStatisticsRootEndpoint):
    """
    "/get_spawn_details"
    """

    # TODO: Auth
    async def get(self):

        area_id: Optional[int] = self._request.query.get("id")
        event_id: Optional[int] = self._request.query.get("eventid")
        mode: Optional[str] = self._request.query.get("mode")
        index: Optional[int] = self._request.query.get("index")
        if not index:
            index = 0
        older_than_x_days: Optional[int] = None
        today_only = False

        if str(mode) == "OLD":
            older_than_x_days = self.outdatedays
        elif str(mode) == "ALL":
            older_than_x_days = None
            today_only = False
        else:
            today_only = True
        spawn_details_helper = await self._get_spawn_details_helper(area_id=area_id, event_id=event_id,
                                                                    older_than_x_days=older_than_x_days,
                                                                    today_only=today_only,
                                                                    index=index)
        return await self._json_response(spawn_details_helper)
