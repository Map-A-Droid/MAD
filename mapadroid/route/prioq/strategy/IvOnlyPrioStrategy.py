from typing import List, Optional, Tuple

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.helper.PokemonHelper import PokemonHelper
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.route.prioq.strategy.AbstractRoutePriorityQueueStrategy import (
    AbstractRoutePriorityQueueStrategy, RoutePriorityQueueEntry)
from mapadroid.route.routecalc.ClusteringHelper import (ClusteringHelper,
                                                        TimedLocation)
from mapadroid.utils.collections import Location


class IvOnlyPrioStrategy(AbstractRoutePriorityQueueStrategy):
    def __init__(self, clustering_timedelta: int, clustering_distance: int, clustering_count_per_circle: int,
                 max_backlog_duration: int, db_wrapper: DbWrapper, geofence_helper: GeofenceHelper,
                 min_time_left_seconds: int, mon_ids_to_scan: Optional[List[int]],
                 delay_after_event: int):
        super().__init__(update_interval=30, full_replace_queue=False,
                         max_backlog_duration=max_backlog_duration,
                         delay_after_event=delay_after_event)
        self._clustering_helper = ClusteringHelper(clustering_distance,
                                                   max_count_per_circle=clustering_count_per_circle,
                                                   max_timedelta_seconds=clustering_timedelta)
        self._db_wrapper: DbWrapper = db_wrapper
        self._geofence_helper: GeofenceHelper = geofence_helper
        self._min_time_left_seconds: int = min_time_left_seconds
        self._mon_ids_iv: Optional[List[int]] = mon_ids_to_scan
        self._encounter_ids_left: List[int] = []

    def get_encounter_ids_left(self) -> List[int]:
        return self._encounter_ids_left

    async def retrieve_new_coords(self) -> List[RoutePriorityQueueEntry]:
        async with self._db_wrapper as session, session:
            next_spawns: List[Tuple[int, Location, int]] = await PokemonHelper.get_to_be_encountered(session,
                                                                                                     geofence_helper=self._geofence_helper,
                                                                                                     min_time_left_seconds=self._min_time_left_seconds,
                                                                                                     eligible_mon_ids=self._mon_ids_iv)
        new_coords: List[RoutePriorityQueueEntry] = []
        self._encounter_ids_left.clear()
        for spawn in next_spawns:
            (timestamp_due, location, encounter_id) = spawn
            self._encounter_ids_left.append(encounter_id)
            entry: RoutePriorityQueueEntry = RoutePriorityQueueEntry(timestamp_due=timestamp_due,
                                                                     location=location)
            new_coords.append(entry)
        return new_coords

    def filter_queue(self, queue: List[RoutePriorityQueueEntry]) -> List[RoutePriorityQueueEntry]:
        return queue

    def is_full_replace_queue(self) -> bool:
        return True

    def postprocess_coords(self, coords: List[RoutePriorityQueueEntry]) -> List[RoutePriorityQueueEntry]:
        locations_transformed_for_clustering: List[TimedLocation] = []
        for entry in coords:
            locations_transformed_for_clustering.append(TimedLocation(entry.timestamp_due, entry.location))
        clustered: List[TimedLocation] = self._clustering_helper.get_clustered(locations_transformed_for_clustering)
        del locations_transformed_for_clustering
        new_coords: List[RoutePriorityQueueEntry] = []
        for clustered_loc in clustered:
            entry: RoutePriorityQueueEntry = RoutePriorityQueueEntry(
                timestamp_due=clustered_loc.relevant_time + self.get_delay_after_event(),
                location=clustered_loc.location)
            new_coords.append(entry)
        return new_coords
