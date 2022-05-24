from typing import List, Tuple, Optional

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.helper.PokemonHelper import PokemonHelper
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.route.prioq.strategy.AbstractRoutePriorityQueueStrategy import AbstractRoutePriorityQueueStrategy, \
    RoutePriorityQueueEntry
from mapadroid.route.routecalc.ClusteringHelper import ClusteringHelper
from mapadroid.utils.collections import Location


class IvOnlyPrioStrategy(AbstractRoutePriorityQueueStrategy):
    def __init__(self, clustering_timedelta: int, clustering_distance: int, clustering_count_per_circle: int,
                 max_backlog_duration: int, db_wrapper: DbWrapper, geofence_helper: GeofenceHelper,
                 min_time_left_seconds: int, mon_ids_to_scan: Optional[List[int]],
                 delay_after_event: int):
        super().__init__(update_interval=600, full_replace_queue=False,
                         max_backlog_duration=max_backlog_duration,
                         delay_after_event=delay_after_event)
        self._clustering_helper = ClusteringHelper(clustering_distance,
                                                   max_count_per_circle=clustering_count_per_circle,
                                                   max_timedelta_seconds=clustering_timedelta)
        self._db_wrapper: DbWrapper = db_wrapper
        self._geofence_helper: GeofenceHelper = geofence_helper
        self._min_time_left_seconds: int = min_time_left_seconds
        self._mon_ids_iv: Optional[List[int]] = mon_ids_to_scan

    async def retrieve_new_coords(self) -> List[RoutePriorityQueueEntry]:
        async with self._db_wrapper as session, session:
            next_spawns: List[Tuple[int, Location]] = await PokemonHelper.get_to_be_encountered(session,
                                                                                                geofence_helper=self._geofence_helper,
                                                                                                min_time_left_seconds=self._min_time_left_seconds,
                                                                                                eligible_mon_ids=self._mon_ids_iv)
        new_coords: List[RoutePriorityQueueEntry] = []
        for spawn in next_spawns:
            (timestamp_due, location) = spawn
            entry: RoutePriorityQueueEntry = RoutePriorityQueueEntry(timestamp_due=timestamp_due,
                                                                     location=location)
            new_coords.append(entry)
        return new_coords

    def filter_queue(self, queue: List[RoutePriorityQueueEntry]) -> List[RoutePriorityQueueEntry]:
        return queue

    def is_full_replace_queue(self) -> bool:
        return True

    def postprocess_coords(self, coords: List[RoutePriorityQueueEntry]) -> List[RoutePriorityQueueEntry]:
        locations_transformed_for_clustering: List[Tuple[int, Location]] = []
        for entry in coords:
            locations_transformed_for_clustering.append((entry.timestamp_due, entry.location))
        clustered = self._clustering_helper.get_clustered(locations_transformed_for_clustering)
        del locations_transformed_for_clustering
        new_coords: List[RoutePriorityQueueEntry] = []
        for (timestamp_due, location) in clustered:
            entry: RoutePriorityQueueEntry = RoutePriorityQueueEntry(
                timestamp_due=timestamp_due + self.get_delay_after_event(),
                location=location)
            new_coords.append(entry)
        return new_coords
