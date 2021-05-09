from datetime import datetime
from typing import List, Optional, Tuple, Dict

from loguru import logger

from mapadroid.db.helper.PokemonHelper import PokemonHelper
from mapadroid.db.helper.TrsStatusHelper import TrsStatusHelper
from mapadroid.db.model import Pokemon, TrsStatsDetectMonRaw
from mapadroid.madmin.endpoints.routes.statistics.AbstractStatistictsRootEndpoint import AbstractStatisticsRootEndpoint
from mapadroid.utils.language import get_mon_name


class GetStatusEndpoint(AbstractStatisticsRootEndpoint):
    """
    "/get_status"
    """

    # TODO: Auth
    async def get(self):
        stats = await TrsStatusHelper.get_all_of_instance(self._session, self._get_instance_id())
        return self._json_response(stats)
