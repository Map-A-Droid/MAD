from typing import Optional, Tuple, Dict, List

from mapadroid.db.helper.PokemonHelper import PokemonHelper
from mapadroid.db.helper.TrsEventHelper import TrsEventHelper
from mapadroid.db.helper.TrsSpawnHelper import TrsSpawnHelper
from mapadroid.db.model import TrsSpawn, TrsEvent
from mapadroid.madmin.endpoints.routes.statistics.AbstractStatistictsRootEndpoint import AbstractStatisticsRootEndpoint
from mapadroid.madmin.functions import get_geofences, generate_coords_from_geofence
from mapadroid.utils.collections import Location


class GetNonivEncountersCountEndpoint(AbstractStatisticsRootEndpoint):
    """
    "/get_noniv_encounters_count"
    """

    # TODO: Auth
    async def get(self):
        minutes: Optional[int] = self._request.query.get("minutes_spawn")
        if minutes:
            minutes = 240
        data: List[Tuple[int, Location]] = await PokemonHelper.get_noniv_encounters_count(self._session,
                                                                                          last_n_minutes=minutes)
        # TODO: Maybe a __str__ for Location is needed
        stats = {'data': data}
        return self._json_response(stats)
