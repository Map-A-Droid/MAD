from typing import Optional, List

from mapadroid.db.helper.TrsEventHelper import TrsEventHelper
from mapadroid.db.helper.TrsSpawnHelper import TrsSpawnHelper
from mapadroid.db.model import TrsSpawn
from mapadroid.madmin.endpoints.routes.statistics.AbstractStatistictsRootEndpoint import AbstractStatisticsRootEndpoint


class ConvertSpawnsEndpoint(AbstractStatisticsRootEndpoint):
    """
    "/convert_spawns"
    """

    # TODO: Auth
    # TODO: DELETE-method?
    async def get(self):
        area_id: Optional[int] = self._request.query.get("id")
        event_id: Optional[int] = self._request.query.get("eventid")
        today_only: Optional[bool] = self._request.query.get("todayonly")
        index: Optional[int] = self._request.query.get("index")
        if not index:
            index = 0

        if await TrsEventHelper.is_event_active(self._session, event_id):
            if today_only:
                await self._add_notice_message('Cannot convert spawnpoints during an event')
                await self._redirect(self._url_for('statistics_spawns'))
            return await self._json_response({'status': 'event'})
        if area_id and event_id:
            spawns: List[TrsSpawn] = await self._get_spawnpoints_of_event(area_id, event_id, today_only=today_only,
                                                                          index=index)
            spawn_ids: List[int] = [spawn.spawnpoint for spawn in spawns]
            await TrsSpawnHelper.convert_spawnpoints(self._session, spawn_ids)
        if today_only:
            await self._add_notice_message('Successfully converted spawnpoints')
            await self._redirect(self._url_for('statistics_spawns'))
            await self._redirect(self._url_for('statistics_spawns'))
        return await self._json_response({'status': 'success'})
