from typing import Optional, Dict

from mapadroid.db.helper.TrsEventHelper import TrsEventHelper
from mapadroid.db.helper.TrsSpawnHelper import TrsSpawnHelper
from mapadroid.db.model import TrsSpawn
from mapadroid.madmin.endpoints.routes.statistics.AbstractStatistictsRootEndpoint import AbstractStatisticsRootEndpoint


class DeleteSpawnEndpoint(AbstractStatisticsRootEndpoint):
    """
    "/delete_spawn"
    """

    # TODO: Auth
    # TODO: DELETE-method?
    async def get(self):
        spawn_id: Optional[int] = self._request.query.get("id")
        area_id: Optional[int] = self._request.query.get("area_id")
        event_id: Optional[int] = self._request.query.get("event_id")
        event: Optional[str] = self._request.query.get("event_id")

        if await TrsEventHelper.is_event_active(self._session, event_id):
            await self._add_notice_message('Event is still active - cannot delete this spawnpoint now.')
        elif spawn_id:
            spawn: Optional[TrsSpawn] = await TrsSpawnHelper.get(self._session, spawn_id)
            if spawn:
                self._delete(spawn)
        query: Dict[str, str] = {"id": area_id,
                                 "eventid": event_id,
                                 "event": event}
        await self._redirect(self._url_for('spawn_details', query_=query), commit=True)
