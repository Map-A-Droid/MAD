import asyncio
import concurrent
import random
from typing import Optional, Dict, List

from loguru import logger

from mapadroid.db.helper.PokemonHelper import PokemonHelper
from mapadroid.db.model import Pokemon
from mapadroid.madmin.AbstractMadminRootEndpoint import AbstractMadminRootEndpoint
from mapadroid.madmin.functions import get_bound_params
from mapadroid.utils.collections import Location
from mapadroid.utils.language import get_mon_name_sync
from mapadroid.utils.madGlobals import MonSeenTypes


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
                                                      old_ne_corner=Location(o_ne_lat,
                                                                             o_ne_lng) if o_ne_lat and o_ne_lng else None,
                                                      old_sw_corner=Location(o_sw_lat,
                                                                             o_sw_lng) if o_sw_lat and o_sw_lng else None,
                                                      timestamp=timestamp)
        loop = asyncio.get_running_loop()
        #with concurrent.futures.ThreadPoolExecutor() as pool:
        mons_serialized = await loop.run_in_executor(
            None, self.__serialize_mons, data)

        return await self._json_response(mons_serialized)

    def __serialize_mons(self, data):
        mons_serialized: List[Dict] = []
        mon_name_cache: Dict[int, str] = self._get_mon_name_cache()
        for mon in data:
            serialized_entry = self.__serialize_single_mon(mon, mon_name_cache)
            mons_serialized.append(serialized_entry)
        return mons_serialized

    @staticmethod
    def __serialize_single_mon(mon, mon_name_cache):
        serialized_entry: Dict = {x: y for x, y in vars(mon).items() if not x.startswith("_")}
        serialized_entry["disappear_time"] = int(mon.disappear_time.timestamp())
        if mon.last_modified:
            serialized_entry["last_modified"] = int(mon.last_modified.timestamp())
        else:
            serialized_entry["last_modified"] = 0
        if mon.seen_type in (MonSeenTypes.NEARBY_STOP.value, MonSeenTypes.NEARBY_CELL.value):
            serialized_entry["latitude"] = float(serialized_entry["latitude"]) + random.uniform(-0.0003, 0.0003)
            serialized_entry["longitude"] = float(serialized_entry["longitude"]) + random.uniform(-0.0005, 0.0005)
        try:
            if mon.pokemon_id in mon_name_cache:
                mon_name = mon_name_cache[mon.pokemon_id]
            else:
                mon_name = get_mon_name_sync(mon.pokemon_id)
                mon_name_cache[mon.pokemon_id] = mon_name

            serialized_entry["name"] = mon_name
        except Exception as e:
            logger.exception(e)
        return serialized_entry
