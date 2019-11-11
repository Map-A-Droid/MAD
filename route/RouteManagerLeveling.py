import collections
import time
from typing import List
from db.DbWrapper import DbWrapper
from route.RouteManagerBase import RoutePoolEntry
from route.RouteManagerQuests import RouteManagerQuests
from utils.logging import logger
from utils.collections import LocationWithVisits, Location


class RouteManagerLeveling(RouteManagerQuests):
    def generate_stop_list(self):
        time.sleep(5)
        stops, stops_with_visits = self.db_wrapper.stop_from_db_without_quests(
            self.geofence_helper, True)

        logger.info('Detected stops without quests: {}', str(len(stops_with_visits)))
        logger.debug('Detected stops without quests: {}', str(stops_with_visits))
        self._stoplist: List[Location] = stops
        self._stops_with_visits: List[LocationWithVisits] = stops_with_visits

    def __worker_changed_update_routepools(self):
        with self._manager_mutex:
            logger.debug("Updating all routepools")
            if len(self._workers_registered) == 0:
                logger.info("No registered workers, aborting __worker_changed_update_routepools...")
                return False

        _, stops_with_visits = self.db_wrapper.stop_from_db_without_quests(
            self.geofence_helper, True)
        any_at_all = False
        for origin in self._routepool:
            origin_local_list = []
            entry: RoutePoolEntry = self._routepool[origin]

            for coord in stops_with_visits:
                if origin not in str(coord.visited_by):
                    origin_local_list.append(Location(coord.lat, coord.lng))

            # subroute is all stops unvisited
            entry.subroute = origin_local_list
            # let's clean the queue just to make sure
            entry.queue.clear()
            any_at_all = len(origin_local_list) > 0 or any_at_all
        return any_at_all

    def __init__(self, db_wrapper: DbWrapper, dbm, area_id, coords: List[Location], max_radius: float,
                 max_coords_within_radius: int, path_to_include_geofence: str, path_to_exclude_geofence: str,
                 routefile: str, mode=None, init: bool = False, name: str = "unknown", settings: dict = None,
                 level: bool = False, calctype: str = "optimized", joinqueue=None):
        RouteManagerQuests.__init__(self, db_wrapper=db_wrapper, dbm=dbm, area_id=area_id, coords=coords,
                                    max_radius=max_radius, max_coords_within_radius=max_coords_within_radius,
                                    path_to_include_geofence=path_to_include_geofence,
                                    path_to_exclude_geofence=path_to_exclude_geofence,
                                    routefile=routefile, init=init,
                                    name=name, settings=settings, mode=mode, level=level, calctype=calctype,
                                    joinqueue=joinqueue
                                    )
        self._stops_with_visits: List[LocationWithVisits] = []

    def _check_coords_before_returning(self, lat, lng, origin):
        if self.init:
            logger.debug('Init Mode - coord is valid')
            return True
        stop = Location(lat, lng)
        logger.info('Checking Stop with ID {}', str(stop))
        if stop not in self._stoplist:
            logger.info('Stop is not in stoplist, either no longer in route or spun already...')
            return False

        if self._stops_with_visits is None or len(self._stops_with_visits) == 0:
            logger.info('no visit info so lets go')
            return True

        for stop in self._stops_with_visits:
            if stop.lat == lat and stop.lng == lng and stop.visited_by is not None and origin in stop.visited_by:
                logger.info("DB says we Already spun stop, ignore it...")
                return False

        logger.info('Getting new Stop')
        return True
