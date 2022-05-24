from typing import Dict, Tuple, Set

from mapadroid.db.helper.TrsSpawnHelper import TrsSpawnHelper
from mapadroid.db.model import TrsSpawn, TrsEvent
from mapadroid.madmin.endpoints.routes.statistics.AbstractStatistictsRootEndpoint import AbstractStatisticsRootEndpoint
from mapadroid.madmin.functions import get_geofences, generate_coords_from_geofence


class DeleteUnfencedSpawnsEndpoint(AbstractStatisticsRootEndpoint):
    """
    "/delete_unfenced_spawns"
    """

    # TODO: Auth
    # TODO: DELETE-method?
    async def get(self):
        processed_fences = []
        spawns: Set[int] = set()
        possible_fences = await get_geofences(self._get_mapping_manager(),)
        for possible_fence in possible_fences:
            for subfence in possible_fences[possible_fence]['include']:
                if subfence in processed_fences:
                    continue
                processed_fences.append(subfence)
                fence = await generate_coords_from_geofence(self._get_mapping_manager(), subfence)
                spawns_of_fence: Dict[int, Tuple[TrsSpawn, TrsEvent]] = await TrsSpawnHelper \
                    .download_spawns(self._session, fence=fence)
                for spawn_id in spawns_of_fence.keys():
                    spawns.add(spawn_id)

        await TrsSpawnHelper.delete_all_except(self._session, spawns)
        return await self._json_response({'status': 'success'})
