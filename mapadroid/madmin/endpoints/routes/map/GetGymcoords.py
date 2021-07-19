from datetime import datetime, timezone
from typing import List, Optional, Dict, Tuple

from mapadroid.db.helper.GymHelper import GymHelper
from mapadroid.db.model import Gym, GymDetail, Raid
from mapadroid.madmin.AbstractMadminRootEndpoint import AbstractMadminRootEndpoint
from mapadroid.madmin.functions import get_bound_params
from mapadroid.utils.collections import Location


class GetGymcoordsEndpoint(AbstractMadminRootEndpoint):
    """
    "/get_gymcoords"
    """

    # TODO: Auth
    async def get(self):
        ne_lat, ne_lng, sw_lat, sw_lng, o_ne_lat, o_ne_lng, o_sw_lat, o_sw_lng = get_bound_params(self._request)
        timestamp: Optional[int] = self._request.query.get("timestamp")
        if timestamp:
            timestamp = int(timestamp)
        coords: List[Dict] = []
        data: Dict[int, Tuple[Gym, GymDetail, Raid]] = \
            await GymHelper.get_gyms_in_rectangle(self._session,
                                                  ne_corner=Location(ne_lat, ne_lng),
                                                  sw_corner=Location(sw_lat, sw_lng),
                                                  old_ne_corner=Location(o_ne_lat, o_ne_lng),
                                                  old_sw_corner=Location(o_sw_lat, o_sw_lng),
                                                  timestamp=timestamp)

        for gym_id, (gym, gym_detail, raid) in data.items():
            raid_data = None
            # TODO: Validate time of spawn/end/start
            if raid and raid.end > datetime.now():
                raid_data = {
                    "spawn": int(raid.spawn.replace(tzinfo=timezone.utc).timestamp()),
                    "start": int(raid.start.replace(tzinfo=timezone.utc).timestamp()),
                    "end": int(raid.end.replace(tzinfo=timezone.utc).timestamp()),
                    "mon": raid.pokemon_id,
                    "form": raid.form,
                    "level": raid.level,
                    "costume": raid.costume,
                    "evolution": raid.evolution
                }

            coords.append({
                "id": gym_id,
                "name": gym_detail.name,
                "img": gym_detail.url,
                "lat": gym.latitude,
                "lon": gym.longitude,
                "team_id": gym.team_id,
                "last_updated": gym.last_modified.replace(tzinfo=timezone.utc).timestamp(),
                "last_scanned": gym.last_scanned.replace(tzinfo=timezone.utc).timestamp(),
                "raid": raid_data
            })

        return await self._json_response(coords)
