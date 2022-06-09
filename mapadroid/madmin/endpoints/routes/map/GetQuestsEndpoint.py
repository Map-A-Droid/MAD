from typing import Dict, Optional, Tuple

from mapadroid.db.helper.PokestopHelper import PokestopHelper
from mapadroid.db.model import Pokestop, TrsQuest
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.madmin.AbstractMadminRootEndpoint import \
    AbstractMadminRootEndpoint
from mapadroid.madmin.functions import (generate_coords_from_geofence,
                                        get_bound_params)
from mapadroid.utils.collections import Location
from mapadroid.utils.questGen import QuestGen


class GetQuestsEndpoint(AbstractMadminRootEndpoint):
    """
    "/get_quests"
    """

    # TODO: Auth
    async def get(self):
        quests = []

        fence_name = self._request.query.get("fence")
        fence: Optional[Tuple[str, Optional[GeofenceHelper]]] = None
        if fence_name not in (None, 'None', 'All'):
            fence: Tuple[str, Optional[GeofenceHelper]] = await generate_coords_from_geofence(
                self._get_mapping_manager(), fence_name)
        ne_lat, ne_lng, sw_lat, sw_lng, o_ne_lat, o_ne_lng, o_sw_lat, o_sw_lng = get_bound_params(self._request)
        timestamp: Optional[int] = self._request.query.get("timestamp")
        if timestamp:
            timestamp = int(timestamp)
        data: Dict[int, Tuple[Pokestop, Dict[int, TrsQuest]]] = \
            await PokestopHelper.get_with_quests(self._session,
                                                 ne_corner=Location(ne_lat, ne_lng),
                                                 sw_corner=Location(sw_lat, sw_lng),
                                                 old_ne_corner=Location(o_ne_lat, o_ne_lng),
                                                 old_sw_corner=Location(o_sw_lat, o_sw_lng),
                                                 timestamp=timestamp,
                                                 fence=fence)
        quest_gen: QuestGen = self._get_quest_gen()
        for stop_id, (stop, quests_of_stop) in data.items():
            for quest in quests_of_stop.values():
                quests.append(await quest_gen.generate_quest(stop, quest))
        del data
        resp = await self._json_response(quests)
        del quests
        return resp
