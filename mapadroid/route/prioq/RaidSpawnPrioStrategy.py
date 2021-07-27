from typing import List, Optional, Tuple

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.helper.RaidHelper import RaidHelper
from mapadroid.db.helper.TrsSpawnHelper import TrsSpawnHelper
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.route.prioq.AbstractRoutePriorityQueueStrategy import AbstractRoutePriorityQueueStrategy, \
    RoutePriorityQueueEntry
from mapadroid.route.routecalc.ClusteringHelper import ClusteringHelper
from mapadroid.utils.collections import Location


class RaidSpawnPrioStrategy(AbstractRoutePriorityQueueStrategy):
    # TODO: Delay after event setting...
    def __init__(self, clustering_timedelta: int, clustering_distance: int, clustering_count_per_circle: int,
                 max_backlog_duration: int, db_wrapper: DbWrapper, geofence_helper: GeofenceHelper):
        super().__init__(update_interval=600, full_replace_queue=False,
                         max_backlog_duration=max_backlog_duration)
        self._clustering_helper = ClusteringHelper(clustering_distance,
                                                   max_count_per_circle=clustering_count_per_circle,
                                                   max_timedelta_seconds=clustering_timedelta)
        self._db_wrapper: DbWrapper = db_wrapper
        self._geofence_helper: GeofenceHelper = geofence_helper

    async def retrieve_new_coords(self) -> List[RoutePriorityQueueEntry]:
        async with self._db_wrapper as session, session:
            next_spawns: List[Tuple[int, Location]] = await RaidHelper.get_next_hatches(session, self._geofence_helper,
                                                                                        only_next_n_seconds=self.get_update_interval())
        new_coords: List[RoutePriorityQueueEntry] = []
        for (timestamp_due, location) in next_spawns:
            entry: RoutePriorityQueueEntry = RoutePriorityQueueEntry(timestamp_due=timestamp_due,
                                                                     location=location)
            new_coords.append(entry)
        return new_coords

    def filter_queue(self, queue: List[RoutePriorityQueueEntry]) -> List[RoutePriorityQueueEntry]:
        # TODO: Cross check against already hatched / scanned by other areas
        return queue

    def postprocess_coords(self, coords: List[RoutePriorityQueueEntry]) -> List[RoutePriorityQueueEntry]:
        locations_transformed_for_clustering: List[Tuple[int, Location]] = []
        for entry in coords:
            locations_transformed_for_clustering.append((entry.timestamp_due, entry.location))
        clustered = self._clustering_helper.get_clustered(locations_transformed_for_clustering)
        del locations_transformed_for_clustering
        new_coords: List[RoutePriorityQueueEntry] = []
        for (timestamp_due, location) in clustered:
            entry: RoutePriorityQueueEntry = RoutePriorityQueueEntry(timestamp_due=timestamp_due,
                                                                     location=location)
            new_coords.append(entry)
        return new_coords
