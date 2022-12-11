import collections
import math
from abc import ABC
from operator import itemgetter
from typing import List, Dict, Optional, Collection

from mapadroid.route.RouteManagerBase import RouteManagerBase
from mapadroid.route.RoutePoolEntry import RoutePoolEntry
from mapadroid.utils.collections import Location
from mapadroid.utils.geo import get_distance_of_two_points_in_meters
from mapadroid.utils.logging import get_logger, LoggerEnums

logger = get_logger(LoggerEnums.routemanager)


class SubrouteReplacingMixin(RouteManagerBase, ABC):
    async def _worker_changed_update_routepools(self, routepool: Dict[str, RoutePoolEntry]) \
            -> Optional[Dict[str, RoutePoolEntry]]:
        if not self._may_update_routepool() and not self._current_route_round_coords:
            logger.info("No coords left to calculate subroutes of")
            return None
        elif not self._may_update_routepool():
            logger.info('Not updating routepools due to area type not supporting subroutes (e.g. IV)')
            return routepool
        elif not routepool:
            logger.info("Routepool passed is empty")
            return None
        coords_to_use: List[Location] = [location for location in self._current_route_round_coords
                                         if location not in self._coords_to_be_ignored]
        logger.info("Calculating routepool for current route of length {} for {} routepool entries",
                    len(coords_to_use), len(routepool))
        new_subroute_length = math.floor(len(coords_to_use) /
                                         len(routepool))
        reduced_routepools = [(origin, routepool[origin].time_added) for origin in
                              routepool]
        sorted_routepools = sorted(reduced_routepools, key=itemgetter(1))
        if new_subroute_length == 0:
            # recursively update the routepool until a single worker handles the leftover coords
            reduced_routepool_to_process = {origin: routepool[origin] for origin, time_added in sorted_routepools[:-1]}
            return await self._worker_changed_update_routepools(reduced_routepool_to_process)

        extra_length_workers = len(coords_to_use) % len(routepool)
        i: int = 0
        temp_total_round: collections.deque = collections.deque(coords_to_use)

        if extra_length_workers > 0:
            logger.debug("New subroute length: {}-{}", new_subroute_length, new_subroute_length + 1)
        else:
            logger.debug("New subroute length: {}", new_subroute_length)

        # we want to order the dict by the time's we added the workers to the areas
        # we first need to build a list of tuples with only origin, time_added
        logger.debug("Checking routepools in the following order: {}", sorted_routepools)
        for origin, _time_added in sorted_routepools:
            entry: RoutePoolEntry = routepool[origin]
            logger.debug("Collecting new subroute for {}", origin)
            # let's assume a worker has already been removed or added to the dict (keys)...

            new_subroute: List[Location] = []
            subroute_index: int = 0
            new_subroute_actual_length = new_subroute_length
            if i < extra_length_workers:
                new_subroute_actual_length += 1
            while len(temp_total_round) > 0 and subroute_index < new_subroute_actual_length:
                subroute_index += 1
                new_subroute.append(temp_total_round.popleft())

            i += 1
            logger.debug("Replacing subroute of {}", origin)
            entry.subroute = new_subroute
            # Set the queue for the new subroute accordingly
            # Search for the closest spot within old queue and only start from there
            closest_to_old_queue: Optional[Location] = self._find_closest_location(
                next(iter(entry.queue)) if entry.queue else None,
                new_subroute)
            entry.queue.clear()
            if not closest_to_old_queue:
                [entry.queue.append(i) for i in new_subroute]
            else:
                found: bool = False
                for loc in new_subroute:
                    if loc == closest_to_old_queue:
                        found = True
                    if found:
                        entry.queue.append(loc)

        logger.debug("Done updating subroutes")
        return routepool

    def _find_closest_location(self, location: Optional[Location], route: Collection[Location]) -> Optional[Location]:
        if not route or not location:
            return None
        closest: Location = next(iter(route))
        closest_distance: float = get_distance_of_two_points_in_meters(location.lat, location.lng,
                                                                       closest.lat, closest.lng)
        for loc in route[1:]:
            distance_to_loc_in_route: float = get_distance_of_two_points_in_meters(location.lat, location.lng,
                                                                                   loc.lat, loc.lng)
            if distance_to_loc_in_route < closest_distance:
                closest = loc
                closest_distance = distance_to_loc_in_route
        return closest
