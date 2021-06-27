from datetime import timezone
from typing import Optional, Dict, List

from mapadroid.db.helper.PokemonHelper import PokemonHelper
from mapadroid.db.model import Pokemon
from mapadroid.madmin.AbstractMadminRootEndpoint import AbstractMadminRootEndpoint
from mapadroid.madmin.functions import get_bound_params
from mapadroid.utils.collections import Location
from mapadroid.utils.language import get_mon_name


class GetMapMonsEndpoint(AbstractMadminRootEndpoint):
    """
    "/get_map_mons"
    """

    # TODO: Auth
    async def get(self):
        ne_lat, ne_lng, sw_lat, sw_lng, o_ne_lat, o_ne_lng, o_sw_lat, o_sw_lng = get_bound_params(self._request)
        timestamp: Optional[int] = self._request.query.get("timestamp")
        if timestamp:
            timestamp = int(timestamp)
        data: List[Pokemon] = \
            await PokemonHelper.get_mons_in_rectangle(self._session,
                                                      ne_corner=Location(ne_lat, ne_lng),
                                                      sw_corner=Location(sw_lat, sw_lng),
                                                      old_ne_corner=Location(o_ne_lat, o_ne_lng),
                                                      old_sw_corner=Location(o_sw_lat, o_sw_lng),
                                                      timestamp=timestamp)

        mons_serialized: List[Dict] = []
        mon_name_cache: Dict[int, str] = {}
        for mon in data:
            serialized_entry: Dict = {x: y for x, y in vars(mon).items() if not x.startswith("_")}
            serialized_entry["disappear_time"] = int(mon.disappear_time.replace(tzinfo=timezone.utc).timestamp())
            if mon.last_modified:
                serialized_entry["last_modified"] = int(mon.last_modified.replace(tzinfo=timezone.utc).timestamp())
            else:
                serialized_entry["last_modified"] = 0
            try:
                if mon.pokemon_id in mon_name_cache:
                    mon_name = mon_name_cache[mon.pokemon_id]
                else:
                    mon_name = await get_mon_name(mon.pokemon_id)
                    mon_name_cache[mon.pokemon_id] = mon_name

                serialized_entry["name"] = mon_name
            except Exception:
                pass
            mons_serialized.append(serialized_entry)

        return self._json_response(mons_serialized)
