from typing import Optional, List

from mapadroid.db.helper.TrsEventHelper import TrsEventHelper
from mapadroid.db.model import TrsSpawn
from mapadroid.madmin.endpoints.routes.statistics.AbstractStatistictsRootEndpoint import AbstractStatisticsRootEndpoint


class DeleteSpawnsEndpoint(AbstractStatisticsRootEndpoint):
    """
    "/delete_spawns"
    """

    # TODO: Auth
    # TODO: DELETE-method?
    async def get(self):
        area_id: Optional[int] = self._request.query.get("id")
        event_id: Optional[int] = self._request.query.get("eventid")
        older_than_x_days: Optional[int] = self._request.query.get("olderthanxdays")
        index: Optional[int] = self._request.query.get("index")
        if not index:
            index = 0

        if await TrsEventHelper.is_event_active(self._session, event_id) and older_than_x_days is None:
            return await self._json_response({'status': 'event'})
        if area_id is not None and event_id is not None:
            spawnpoints: List[TrsSpawn] = await self._get_spawnpoints_of_event(area_id, event_id,
                                                                               older_than_x_days=older_than_x_days,
                                                                               index=index)
            for spawn in spawnpoints:
                await self._delete(spawn)
        if older_than_x_days is not None:
            await self._add_notice_message('Successfully deleted outdated spawnpoints')
            await self._redirect(self._url_for('statistics_spawns'), commit=True)
        return await self._json_response({'status': 'success'})
