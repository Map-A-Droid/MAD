from typing import List
import numpy as np
from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.route.RouteManagerBase import RoutePoolEntry
from mapadroid.route.RouteManagerQuests import RouteManagerQuests
from mapadroid.utils.collections import Location
from mapadroid.utils.logging import get_logger, LoggerEnums


logger = get_logger(LoggerEnums.routemanager)


class RouteManagerLevelingRoutefree(RouteManagerQuests):
    def __init__(self, db_wrapper: DbWrapper, dbm, area_id, coords: List[Location], max_radius: float,
                 max_coords_within_radius: int, path_to_include_geofence: str, path_to_exclude_geofence: str,
                 routefile: str, mode=None, init: bool = False, name: str = "unknown", settings: dict = None,
                 level: bool = False, calctype: str = "route", joinqueue=None):
        RouteManagerQuests.__init__(self, db_wrapper=db_wrapper, dbm=dbm, area_id=area_id, coords=coords,
                                    max_radius=max_radius, max_coords_within_radius=max_coords_within_radius,
                                    path_to_include_geofence=path_to_include_geofence,
                                    path_to_exclude_geofence=path_to_exclude_geofence,
                                    routefile=routefile, init=init,
                                    name=name, settings=settings, mode=mode, level=level, calctype=calctype,
                                    joinqueue=joinqueue
                                    )

    def _worker_changed_update_routepools(self):
        with self._manager_mutex and self._workers_registered_mutex:
            self.logger.info("Updating all routepools in level mode for {} origins", len(self._routepool))
            if len(self._workers_registered) == 0:
                self.logger.info("No registered workers, aborting __worker_changed_update_routepools...")
                return False

            any_at_all = False
            for origin in self._routepool:
                origin_local_list = []
                entry: RoutePoolEntry = self._routepool[origin]

                if len(entry.queue) > 0:
                    self.logger.debug("origin {} already has a queue, do not touch...", origin)
                    continue
                current_worker_pos = entry.current_pos
                unvisited_stops = self.db_wrapper.get_nearest_stops_from_position(geofence_helper=self.geofence_helper,
                                                                                  origin=origin,
                                                                                  lat=current_worker_pos.lat,
                                                                                  lon=current_worker_pos.lng,
                                                                                  limit=30,
                                                                                  ignore_spinned=self.settings.get(
                                                                                      "ignore_spinned_stops", True),
                                                                                  maxdistance=5)
                if len(unvisited_stops) == 0:
                    self.logger.info("There are no unvisited stops left in DB for {} - nothing more to do!", origin)
                    continue

                for coord in unvisited_stops:
                    coord_location = Location(coord.lat, coord.lng)
                    if coord_location in self._coords_to_be_ignored:
                        self.logger.info('Already tried this Stop but it failed spinnable test, skip it')
                        continue
                    origin_local_list.append(coord_location)

                if len(unvisited_stops) > 0:
                    self.logger.info("Recalc a route")
                    new_route = self._local_recalc_subroute(unvisited_stops)
                    origin_local_list.clear()
                    for coord in new_route:
                        origin_local_list.append(Location(coord["lat"], coord["lng"]))

                # subroute is all stops unvisited
                self.logger.info("Origin {} has {} unvisited stops for this route", origin, len(origin_local_list))
                entry.subroute = origin_local_list
                # let's clean the queue just to make sure
                entry.queue.clear()
                [entry.queue.append(i) for i in origin_local_list]
                any_at_all = len(origin_local_list) > 0 or any_at_all
                # saving new startposition of walker in db
                newstartposition: Location = entry.queue[0]
                self.db_wrapper.save_last_walker_position(origin=origin,
                                                          lat=newstartposition.lat,
                                                          lng=newstartposition.lng)
            return True

    def _local_recalc_subroute(self, unvisited_stops):
        to_be_route = np.zeros(shape=(len(unvisited_stops), 2))
        for i in range(len(unvisited_stops)):
            to_be_route[i][0] = float(unvisited_stops[i].lat)
            to_be_route[i][1] = float(unvisited_stops[i].lng)
        new_route = self.calculate_new_route(to_be_route, self._max_radius, self._max_coords_within_radius,
                                             False, 1,
                                             True)

        return new_route

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
                self.logger.info('Other worker shutdown route - leaving it')
                return False

            self._worker_changed_update_routepools()
            self._start_calc = False
            return True
        finally:
            self._manager_mutex.release()

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
                self.logger.info("Starting routemanager")

                if self._shutdown_route:
                    self.logger.info('Other worker shutdown route - leaving it')
                    return False

                self._prio_queue = None
                self.delay_after_timestamp_prio = None
                self.starve_route = False
                self._start_check_routepools()

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
        self.logger.info('Shutdown Route')
        if self._is_started:
            self._is_started = False
            self._round_started_time = None
            if self.init:
                self._first_started = False
            self._shutdown_route = False

        # clear not processed stops
        self._stops_not_processed.clear()
        self._coords_to_be_ignored.clear()
        self._stoplist.clear()

    def _check_coords_before_returning(self, lat, lng, origin):
        if self.init:
            self.logger.debug('Init Mode - coord is valid')
            return True
        stop = Location(lat, lng)
        self.logger.info('Checking Stop with ID {}', stop)
        if stop in self._coords_to_be_ignored:
            self.logger.info('Already tried this Stop and failed it')
            return False
        self.logger.info('DB knows nothing of this stop for {} lets try and go there', origin)
        return True
