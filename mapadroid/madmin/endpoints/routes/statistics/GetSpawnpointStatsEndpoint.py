from typing import Dict, Optional, Tuple

from mapadroid.db.helper.TrsSpawnHelper import TrsSpawnHelper
from mapadroid.db.model import TrsEvent, TrsSpawn
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.madmin.endpoints.routes.statistics.AbstractStatistictsRootEndpoint import \
    AbstractStatisticsRootEndpoint
from mapadroid.madmin.functions import (generate_coords_from_geofence,
                                        get_geofences)
from mapadroid.worker.WorkerType import WorkerType


class GetSpawnpointStatsEndpoint(AbstractStatisticsRootEndpoint):
    """
    "/get_spawnpoints_stats"
    """

    # TODO: Auth
    async def get(self):
        geofence_type: Optional[str] = self._request.query.get("type", "mon_mitm")
        if not geofence_type:
            stats = {'spawnpoints': []}
            return await self._json_response(stats)
        try:
            area_worker_type: WorkerType = WorkerType(geofence_type)
        except ValueError:
            stats = {'spawnpoints': []}
            return await self._json_response(stats)

        geofence_id: Optional[int] = int(self._request.query.get("fence", -1))
        coords = []
        known = {}
        unknown = {}
        processed_fences = []
        events = []
        eventidhelper = {}
        if geofence_id != -1:
            possible_fences = await get_geofences(self._get_mapping_manager(),
                                                  area_id_req=geofence_id)
        else:
            possible_fences = await get_geofences(self._get_mapping_manager(),
                                                  worker_type=area_worker_type)

        for possible_fence in possible_fences:
            mode = possible_fences[possible_fence]['mode']
            area_id = possible_fences[possible_fence]['area_id']
            subfenceindex: int = 0

            for subfence in possible_fences[possible_fence]['include']:
                if subfence in processed_fences:
                    continue
                processed_fences.append(subfence)
                fence: Tuple[str, Optional[GeofenceHelper]] = await generate_coords_from_geofence(
                    self._get_mapping_manager(), subfence)
                known.clear()
                unknown.clear()
                events.clear()

                spawns_and_events: Dict[int, Tuple[TrsSpawn, TrsEvent]] = await TrsSpawnHelper \
                    .download_spawns(self._session, fence=fence[0])
                for spawn_id, (spawn, event) in spawns_and_events.items():
                    if event.event_name not in known:
                        known[event.event_name] = []
                    if event.event_name not in unknown:
                        unknown[event.event_name] = []
                    if event.event_name not in events:
                        events.append(event.event_name)
                        eventidhelper[event.event_name] = event.id

                    if spawn.calc_endminsec is None:
                        unknown[event.event_name].append(spawn_id)
                    else:
                        known[event.event_name].append(spawn_id)

                for event in events:
                    today: int = 0
                    outdate: int = 0

                    if event == "DEFAULT":
                        outdate = await self._get_spawn_details_helper(area_id=area_id, event_id=eventidhelper[event],
                                                                       older_than_x_days=self.outdatedays,
                                                                       sum_only=True,
                                                                       index=subfenceindex)
                    else:
                        today = await self._get_spawn_details_helper(area_id=area_id, event_id=eventidhelper[event],
                                                                     today_only=True, sum_only=True,
                                                                     index=subfenceindex)

                    coords.append({'fence': subfence, 'known': len(known[event]), 'unknown': len(unknown[event]),
                                   'sum': len(known[event]) + len(unknown[event]), 'event': event, 'mode': mode,
                                   'area_id': area_id, 'eventid': eventidhelper[event],
                                   'todayspawns': today, 'outdatedspawns': outdate, 'index': subfenceindex
                                   })

                subfenceindex += 1

        stats = {'spawnpoints': coords}
        return await self._json_response(stats)
