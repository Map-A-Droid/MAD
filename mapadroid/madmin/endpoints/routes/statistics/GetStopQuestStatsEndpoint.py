from typing import Dict, List, Optional, Tuple

from mapadroid.db.helper.PokestopHelper import PokestopHelper
from mapadroid.db.helper.TrsQuestHelper import TrsQuestHelper
from mapadroid.db.model import Pokestop, TrsQuest
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.madmin.endpoints.routes.statistics.AbstractStatistictsRootEndpoint import \
    AbstractStatisticsRootEndpoint
from mapadroid.madmin.functions import (generate_coords_from_geofence,
                                        get_geofences)
from mapadroid.utils.collections import Location
from mapadroid.worker.WorkerType import WorkerType


class GetStopQuestStatsEndpoint(AbstractStatisticsRootEndpoint):
    """
    "/get_stop_quest_stats"
    """

    # TODO: Auth
    async def get(self):
        stats_process = []
        processed_fences = []
        possible_fences: Dict[int, Dict] = await get_geofences(self._get_mapping_manager(),
                                                               worker_type=WorkerType.STOPS)
        wanted_fences = []
        if self._get_mad_args().quest_stats_fences != "":
            wanted_fences = [item.lower().replace(" ", "") for item in
                             self._get_mad_args().quest_stats_fences.split(",")]
        for area_id, fence_data in possible_fences.items():
            area_settings: Optional[SettingsAreaPokestop] = await self._get_mapping_manager().routemanager_get_settings(area_id)
            subfenceindex: int = 0

            for include_fence_name, list_of_coords in fence_data["include"].items():
                if include_fence_name in processed_fences:
                    continue

                if len(wanted_fences) > 0:
                    if str(include_fence_name).lower() not in wanted_fences:
                        continue

                processed_fences.append(include_fence_name)
                fence: Tuple[str, Optional[GeofenceHelper]] = await generate_coords_from_geofence(
                    self._get_mapping_manager(), include_fence_name)
                # TODO: Just get tuples with Optional[TrsQuest]?
                stops_in_fence: List[Location] = await PokestopHelper.get_locations_in_fence(self._session,
                                                                                             fence=fence)
                quests_in_fence: Dict[int, Tuple[Pokestop, Dict[int, TrsQuest]]] = await PokestopHelper \
                    .get_with_quests(self._session, fence=fence)
                layer_quests_in_fence = {k: v for k, v in quests_in_fence.items() if area_settings.layer in v[1]}
                stops = len(stops_in_fence)
                # TODO: Consider the different layers having been scanned
                quests = len(layer_quests_in_fence)

                processed: int = 0
                if int(stops) > 0:
                    processed: int = int(int(quests) * 100 / int(stops))
                info = {
                    "fence": str(include_fence_name),
                    'stops': int(stops),
                    'quests': int(quests),
                    'processed': str(int(processed)) + " %"
                }
                stats_process.append(info)

                subfenceindex += 1

        # Quest
        quest: list = []
        quest_db: List[Tuple[int, int]] = await TrsQuestHelper.get_quests_counts(self._session, last_n_days=1)
        for ts, count in quest_db:
            quest_raw = (int(ts * 1000), count)
            quest.append(quest_raw)

        # Stop
        stop = []
        data: List[Tuple[str, int]] = await PokestopHelper.get_stop_quest(self._session)
        for label, timestamp in data:
            stop.append({'label': label, 'data': timestamp})

        stats = {'stop_quest_stats': stats_process, 'quest': quest, 'stop': stop}
        return await self._json_response(stats)
