from typing import Optional, Dict, Tuple

from mapadroid.db.helper.PokestopHelper import PokestopHelper
from mapadroid.db.model import Pokestop, TrsQuest
from mapadroid.madmin.AbstractMadminRootEndpoint import AbstractMadminRootEndpoint
from mapadroid.madmin.functions import get_bound_params, generate_coords_from_geofence
from mapadroid.utils.collections import Location
from mapadroid.utils.questGen import generate_quest


class GetQuestsEndpoint(AbstractMadminRootEndpoint):
    """
    "/get_quests"
    """

    # TODO: Auth
    async def get(self):
        quests = []

        fence = self._request.query.get("fence")
        if fence not in (None, 'None', 'All'):
            fence = generate_coords_from_geofence(self._get_mapping_manager(), self._session, self._get_instance_id(),
                                                  fence)
        else:
            fence = None
        ne_lat, ne_lng, sw_lat, sw_lng, o_ne_lat, o_ne_lng, o_sw_lat, o_sw_lng = get_bound_params(self._request)
        timestamp: Optional[int] = self._request.query.get("timestamp")
        if timestamp:
            timestamp = int(timestamp)
        data: Dict[int, Tuple[Pokestop, TrsQuest]] = \
            await PokestopHelper.get_with_quests(self._session,
                                                 ne_corner=Location(ne_lat, ne_lng),
                                                 sw_corner=Location(sw_lat, sw_lng),
                                                 old_ne_corner=Location(o_ne_lat, o_ne_lng),
                                                 old_sw_corner=Location(o_sw_lat, o_sw_lng),
                                                 timestamp=timestamp,
                                                 fence=fence)

        for stop_id, (stop, quest) in data.items():
            quests.append(await generate_quest(stop, quest))
        del data
        resp = await self._json_response(quests)
        del quests
        return resp
