from typing import Tuple, List, Dict

from mapadroid.db.helper.PokemonHelper import PokemonHelper
from mapadroid.madmin.endpoints.routes.statistics.AbstractStatistictsRootEndpoint import AbstractStatisticsRootEndpoint
from mapadroid.utils.collections import Location


class GetNonivEncountersCountEndpoint(AbstractStatisticsRootEndpoint):
    """
    "/get_noniv_encounters_count"
    """

    # TODO: Auth
    async def get(self):
        minutes = self._get_minutes_usage_query_args()
        data: List[Tuple[int, Location]] = await PokemonHelper.get_noniv_encounters_count(self._session,
                                                                                          last_n_minutes=minutes)
        # TODO: Maybe a __str__ for Location is needed
        data_formatted: List[Dict] = []
        for amount, location in data:
            data_formatted.append({
                "count": amount,
                "location": location,
            })

        stats = {'data': data}
        return await self._json_response(stats)
