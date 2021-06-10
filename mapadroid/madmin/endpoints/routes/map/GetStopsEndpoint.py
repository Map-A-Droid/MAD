from datetime import timezone
from typing import List, Optional, Dict, Tuple

from mapadroid.db.helper.PokestopHelper import PokestopHelper
from mapadroid.db.model import Pokestop, TrsQuest
from mapadroid.madmin.AbstractRootEndpoint import AbstractRootEndpoint
from mapadroid.madmin.functions import get_bound_params
from mapadroid.utils.collections import Location


class GetStopsEndpoint(AbstractRootEndpoint):
    """
    "/get_stops"
    """

    # TODO: Auth
    async def get(self):
        ne_lat, ne_lng, sw_lat, sw_lng, o_ne_lat, o_ne_lng, o_sw_lat, o_sw_lng = get_bound_params(self._request)
        timestamp: Optional[int] = self._request.query.get("timestamp")
        if timestamp:
            timestamp = int(timestamp)
        data: List[Pokestop] = \
            await PokestopHelper.get_in_rectangle(self._session,
                                                  ne_corner=Location(ne_lat, ne_lng),
                                                  sw_corner=Location(sw_lat, sw_lng),
                                                  old_ne_corner=Location(o_ne_lat, o_ne_lng),
                                                  old_sw_corner=Location(o_sw_lat, o_sw_lng),
                                                  timestamp=timestamp)
        stops_with_quests: Dict[int, Tuple[Pokestop, TrsQuest]] = \
            await PokestopHelper.get_with_quests(self._session,
                                                 ne_corner=Location(ne_lat, ne_lng),
                                                 sw_corner=Location(sw_lat, sw_lng),
                                                 old_ne_corner=Location(o_ne_lat, o_ne_lng),
                                                 old_sw_corner=Location(o_sw_lat, o_sw_lng),
                                                 timestamp=timestamp)
        prepared_for_serialization: List[Dict] = []
        for stop in data:
            stop_serialized = {variable: value for variable, value in vars(stop).items() if not variable.startswith("_")}
            stop_serialized["last_modified"] = int(stop.last_modified.replace(tzinfo=timezone.utc).timestamp()) if stop.last_modified else 0
            stop_serialized["lure_expiration"] = int(stop.lure_expiration.replace(tzinfo=timezone.utc).timestamp()) if stop.lure_expiration else 0
            stop_serialized["last_updated"] = int(stop.last_updated.replace(tzinfo=timezone.utc).timestamp()) if stop.last_updated else 0
            stop_serialized["incident_start"] = int(stop.incident_start.replace(tzinfo=timezone.utc).timestamp()) if stop.incident_start else 0
            stop_serialized["incident_expiration"] = int(
                stop.incident_expiration.replace(tzinfo=timezone.utc).timestamp()) if stop.incident_expiration else 0
            stop_serialized["has_quest"] = stop.pokestop_id in stops_with_quests
            prepared_for_serialization.append(stop_serialized)

        return self._json_response(prepared_for_serialization)
