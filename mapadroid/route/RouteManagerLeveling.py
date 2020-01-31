import time
from typing import List

import numpy as np

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.route.RouteManagerBase import RoutePoolEntry
from mapadroid.route.RouteManagerQuests import RouteManagerQuests
from mapadroid.utils.collections import Location
from mapadroid.utils.logging import logger


class RouteManagerLeveling(RouteManagerQuests):
    def __init__(self, db_wrapper: DbWrapper, dbm, area_id, coords: List[Location], max_radius: float,
                 max_coords_within_radius: int, path_to_include_geofence: str, path_to_exclude_geofence: str,
                 routefile: str, mode=None, init: bool = False, name: str = "unknown", settings: dict = None,
                 level: bool = False, calctype: str = "quick", joinqueue=None, ws_server = None):
        RouteManagerQuests.__init__(self, db_wrapper=db_wrapper, dbm=dbm, area_id=area_id, coords=coords,
                                    max_radius=max_radius, max_coords_within_radius=max_coords_within_radius,
                                    path_to_include_geofence=path_to_include_geofence,
                                    path_to_exclude_geofence=path_to_exclude_geofence,
                                    routefile=routefile, init=init,
                                    name=name, settings=settings, mode=mode, level=level, calctype=calctype,
                                    joinqueue=joinqueue, ws_server=ws_server
                                    )

    def worker_changed_update_routepools(self):
        with self._manager_mutex and self._workers_registered_mutex:
            logger.info("Updating all routepools in levelmode for {} origins", len(self._routepool))
            if len(self._workers_registered) == 0:
                logger.info("No registered workers, aborting __worker_changed_update_routepools...")
                return False

            any_at_all = False
            for origin in self._routepool:
                origin_local_list = []
                entry: RoutePoolEntry = self._routepool[origin]

                if len(entry.queue) > 0:
                    logger.debug("origin {} already has a queue, do not touch...", origin)
                    continue
                unvisited_stops = self.db_wrapper.stops_from_db_unvisited(self.geofence_helper, origin)
                if len(unvisited_stops) == 0:
                    logger.info("There are no unvisited stops left in DB for {} - nothing more to do!",
                                origin)
                    continue
                if len(self._route) > 0:
                    logger.info("Making a subroute of unvisited stops..")
                    for coord in self._route:
                        coord_location = Location(coord.lat, coord.lng)
                        if coord_location in self._coords_to_be_ignored:
                            logger.info('Already tried this Stop but it failed spinnable test, skip it')
                            continue
                        if coord_location in unvisited_stops:
                            origin_local_list.append(coord_location)
                if len(origin_local_list) == 0:
                    logger.info("None of the stops in original route was unvisited, recalc a route")
                    new_route = self._local_recalc_subroute(unvisited_stops)
                    for coord in new_route:
                        origin_local_list.append(Location(coord["lat"], coord["lng"]))

                # subroute is all stops unvisited
                logger.info("Origin {} has {} unvisited stops for this route", origin, len(origin_local_list))
                entry.subroute = origin_local_list
                # let's clean the queue just to make sure
                entry.queue.clear()
                [entry.queue.append(i) for i in origin_local_list]
                any_at_all = len(origin_local_list) > 0 or any_at_all
            return any_at_all

    def _local_recalc_subroute(self, unvisited_stops):
        to_be_route = np.zeros(shape=(len(unvisited_stops), 2))
        for i in range(len(unvisited_stops)):
            to_be_route[i][0] = float(unvisited_stops[i].lat)
            to_be_route[i][1] = float(unvisited_stops[i].lng)
        new_route = self.calculate_new_route(to_be_route, self._max_radius, self._max_coords_within_radius,
                                             False, 1,
                                             True)

        return new_route

    def generate_stop_list(self):
        time.sleep(5)
        stops_in_fence = self.db_wrapper.stops_from_db(self.geofence_helper)

        logger.info('Detected stops without quests: {}', str(len(stops_in_fence)))
        logger.debug('Detected stops without quests: {}', str(stops_in_fence))
        self._stoplist: List[Location] = stops_in_fence

    def _retrieve_latest_priority_queue(self):
        return None

    def _get_coords_post_init(self):
        return self.db_wrapper.stops_from_db(self.geofence_helper)

    def _cluster_priority_queue_criteria(self):
        pass

    def _priority_queue_update_interval(self):
        return 0

    def _recalc_route_workertype(self):
        self.recalc_route(self._max_radius, self._max_coords_within_radius, 1, delete_old_route=False,
                          in_memory=True)
        self._init_route_queue()

    def _get_coords_after_finish_route(self) -> bool:
        self._manager_mutex.acquire()
        try:

            if self._shutdown_route:
                logger.info('Other worker shutdown route {} - leaving it', str(self.name))
                return False

            if self._start_calc:
                logger.info("Another process already calculate the new route")
                return True
            self._start_calc = True
            self._restore_original_route()

            any_unvisited = False
            for origin in self._routepool:
                any_unvisited = self.db_wrapper.any_stops_unvisited(self.geofence_helper, origin)
                if any_unvisited:
                    break

            if not any_unvisited:
                logger.info("Not getting any stops - leaving now.")
                self._shutdown_route = True
                self._start_calc = False
                return False

            # Redo individual routes
            self.worker_changed_update_routepools()
            self._start_calc = False
            return True
        finally:
            self._manager_mutex.release()

    def _restore_original_route(self):
        if not self._tempinit:
            logger.info("Restoring original route")
            with self._manager_mutex:
                self._route = self._routecopy.copy()

    def _check_unprocessed_stops(self):
        self._manager_mutex.acquire()

        try:
            # We finish routes on a per walker/origin level, so the route itself is always the same as long as at
            # least one origin is connected to it.
            return self._stoplist
        finally:
            self._manager_mutex.release()

    def _start_routemanager(self):
        self._manager_mutex.acquire()
        try:
            if not self._is_started:
                self._is_started = True
                logger.info("Starting routemanager {}", str(self.name))

                if self._shutdown_route:
                    logger.info('Other worker shutdown route {} - leaving it', str(self.name))
                    return False

                self.generate_stop_list()
                stops = self._stoplist
                self._prio_queue = None
                self.delay_after_timestamp_prio = None
                self.starve_route = False
                self._first_round_finished = False
                self._start_check_routepools()

                if not self._first_started:
                    logger.info(
                        "First starting quest route - copying original route {} for later use",
                        str(self.name))
                    self._routecopy = self._route.copy()
                    self._first_started = True
                else:
                    logger.info("Restoring original route {} ", str(self.name))
                    self._route = self._routecopy.copy()

                new_stops = list(set(stops) - set(self._route))
                if len(new_stops) > 0:
                    logger.info("There's {} new stops not in route", len(new_stops))

                if len(stops) == 0:
                    logger.info('No  Stops detected in route {} - quit worker', str(self.name))
                    self._shutdown_route = True
                    self._restore_original_route()
                    self._route: List[Location] = []
                    return False

                if 0 < len(stops) < len(self._route) \
                        and len(stops) / len(self._route) <= 0.3:
                    # Calculating new route because 70 percent of stops are processed
                    logger.info('There are less stops without quest than routepositions - recalc')
                    self._recalc_stop_route(stops)
                elif len(self._route) == 0 and len(stops) > 0:
                    logger.warning("Something wrong with area {}: it have many new stops "
                                   "- you should delete routefile!!",
                                   str(self.name))
                    logger.info("Recalc new route for area {}", str(self.name))
                    self._recalc_stop_route(stops)
                else:
                    self._init_route_queue()

                logger.info('Getting {} positions in route {}'.format(len(self._route), str(self.name)))
                return True

        finally:
            self._manager_mutex.release()

        return True

    def _recalc_stop_route(self, stops):
        self._clear_coords()
        self.add_coords_list(stops)
        self._overwrite_calculation = True
        self._recalc_route_workertype()
        self._init_route_queue()

    def _delete_coord_after_fetch(self) -> bool:
        return False

    def _quit_route(self):
        logger.info('Shutdown Route {}', str(self.name))
        if self._is_started:
            self._is_started = False
            self._round_started_time = None
            if self.init: self._first_started = False
            self._restore_original_route()
            self._shutdown_route = False

        # clear not processed stops
        self._stops_not_processed.clear()
        self._coords_to_be_ignored.clear()
        self._stoplist.clear()

    def _check_coords_before_returning(self, lat, lng, origin):
        if self.init:
            logger.debug('Init Mode - coord is valid')
            return True
        stop = Location(lat, lng)
        logger.info('Checking Stop with ID {}', str(stop))
        if stop in self._coords_to_be_ignored:
            logger.info('Already tried this Stop and failed it')
            return False
        logger.info('DB knows nothing of this stop for {} lets try and go there', origin)
        return True
