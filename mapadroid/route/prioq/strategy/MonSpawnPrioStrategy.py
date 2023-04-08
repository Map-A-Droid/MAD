from typing import List, Optional, Tuple

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.helper.TrsSpawnHelper import TrsSpawnHelper
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.route.prioq.strategy.AbstractRoutePriorityQueueStrategy import (
    AbstractRoutePriorityQueueStrategy, RoutePriorityQueueEntry)
from mapadroid.route.routecalc.ClusteringHelper import (ClusteringHelper,
                                                        TimedLocation)
from mapadroid.utils.collections import Location
from mapadroid.utils.logging import LoggerEnums, get_logger

logger = get_logger(LoggerEnums.routemanager)


class MonSpawnPrioStrategy(AbstractRoutePriorityQueueStrategy):
    def __init__(self, clustering_timedelta: int, clustering_distance: int, clustering_count_per_circle: int,
                 max_backlog_duration: int, db_wrapper: DbWrapper, geofence_helper: GeofenceHelper,
                 include_event_id: Optional[int], delay_after_event: int):
        super().__init__(update_interval=600, full_replace_queue=False,
                         max_backlog_duration=max_backlog_duration,
                         delay_after_event=delay_after_event)
        self._clustering_helper = ClusteringHelper(clustering_distance,
                                                   max_count_per_circle=clustering_count_per_circle,
                                                   max_timedelta_seconds=clustering_timedelta)
        self._db_wrapper: DbWrapper = db_wrapper
        self._geofence_helper: GeofenceHelper = geofence_helper
        self._include_event_id: Optional[int] = include_event_id

    async def retrieve_new_coords(self) -> List[RoutePriorityQueueEntry]:
        logger.debug("Fetching mon spawn coords")
        async with self._db_wrapper as session, session:
            next_spawns: List[Tuple[int, Location]] = await TrsSpawnHelper.get_next_spawns(session,
                                                                                           self._geofence_helper,
                                                                                           self._include_event_id,
                                                                                           limit_next_n_seconds=self.get_update_interval())
        new_coords: List[RoutePriorityQueueEntry] = []
        for (timestamp_due, location) in next_spawns:
            entry: RoutePriorityQueueEntry = RoutePriorityQueueEntry(timestamp_due=timestamp_due,
                                                                     location=location)
            new_coords.append(entry)
        return new_coords

    def filter_queue(self, queue: List[RoutePriorityQueueEntry]) -> List[RoutePriorityQueueEntry]:
        return queue

    def postprocess_coords(self, coords: List[RoutePriorityQueueEntry]) -> List[RoutePriorityQueueEntry]:
        logger.debug("Post-processing coords")
        try:
            locations_transformed_for_clustering: List[TimedLocation] = []
            for entry in coords:
                locations_transformed_for_clustering.append(TimedLocation(entry.timestamp_due, entry.location))
            clustered: List[TimedLocation] = self._clustering_helper\
                .get_clustered(locations_transformed_for_clustering)
            del locations_transformed_for_clustering
            new_coords: List[RoutePriorityQueueEntry] = []
            for clustered_loc in clustered:
                entry: RoutePriorityQueueEntry = RoutePriorityQueueEntry(
                    timestamp_due=clustered_loc.relevant_time + self.get_delay_after_event(),
                    location=clustered_loc.location)
                new_coords.append(entry)
            return new_coords
        except Exception as e:
            logger.warning("Failed to process coords")
            logger.exception(e)
            return []
