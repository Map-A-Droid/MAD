import collections
import time
from typing import List, Dict

from db.dbWrapperBase import DbWrapperBase
from route.RouteManagerBase import RouteManagerBase
from utils.logging import logger

Location = collections.namedtuple('Location', ['lat', 'lng'])


class RouteManagerQuests(RouteManagerBase):
    def generate_stop_list(self):
        time.sleep(5)
        stops = self.db_wrapper.stop_from_db_without_quests(
            self.geofence_helper, self._level)
        logger.info('Detected stops without quests: {}', str(stops))
        self._stoplist: List[Location] = stops

    def _retrieve_latest_priority_queue(self):
        return None

    def _get_coords_post_init(self):
        return self.db_wrapper.stops_from_db(self.geofence_helper)

    def _cluster_priority_queue_criteria(self):
        pass

    def _priority_queue_update_interval(self):
        return 0

    def _recalc_route_workertype(self):
        if self.init:
            self.recalc_route(self._max_radius, self._max_coords_within_radius, 1, delete_old_route=True,
                              nofile=False)
        else:
            self.recalc_route(self._max_radius, self._max_coords_within_radius, 1, delete_old_route=False,
                              nofile=True)

        self._init_route_queue()

    def __init__(self, db_wrapper: DbWrapperBase, coords: List[Location], max_radius: float,
                 max_coords_within_radius: int, path_to_include_geofence: str, path_to_exclude_geofence: str,
                 routefile: str, mode=None, init: bool = False, name: str = "unknown", settings: dict = None,
                 level: bool = False, calctype: str = "optimized"):
        RouteManagerBase.__init__(self, db_wrapper=db_wrapper, coords=coords, max_radius=max_radius,
                                  max_coords_within_radius=max_coords_within_radius,
                                  path_to_include_geofence=path_to_include_geofence,
                                  path_to_exclude_geofence=path_to_exclude_geofence,
                                  routefile=routefile, init=init,
                                  name=name, settings=settings, mode=mode, level=level, calctype=calctype
                                  )
        self.starve_route = False
        self._stoplist: List[Location] = []

    def _get_coords_after_finish_route(self):
        if self._level:
            logger.info("Level Mode - switch to next area")
            return False
        self._manager_mutex.acquire()
        try:
            if self._start_calc:
                logger.info("Another process already calculate the new route")
                return True
            self._start_calc = True
            if not self._route_queue.empty():
                self._start_calc = False
                return True
            self.generate_stop_list()
            if len(self._stoplist) == 0:
                self._start_calc = False
                return False
            coords: List[Location] = self._check_unprocessed_stops()
            # remove coords to be ignored from coords
            coords = [coord for coord in coords if coord not in self._coords_to_be_ignored]
            if len(coords) > 0:
                self._clear_coords()
                self.add_coords_list(coords)
                self._overwrite_calculation = True
                self._recalc_route_workertype()
                self._start_calc = False
            else:
                self._start_calc = False
                return False
            if len(self._route) == 0:
                return False
            return True
        finally:
            self._manager_mutex.release()

    def _check_unprocessed_stops(self):
        self._manager_mutex.acquire()

        try:
            list_of_stops_to_return: List[Location] = []
            stops_not_processed: Dict[Location, int] = {}

            if len(self._stoplist) == 0:
                return list_of_stops_to_return
            else:
                # we only want to add stops that we haven't spun yet
                for stop in self._stoplist:
                    if stop not in stops_not_processed:
                        stops_not_processed[stop] = 1
                    else:
                        stops_not_processed[stop] += 1

            for stop, error_count in stops_not_processed.items():
                if error_count < 4:
                    logger.warning("Found stop not processed yet: {}".format(str(stop)))
                    list_of_stops_to_return.append(stop)
                else:
                    logger.error("Stop {} has not been processed thrice in a row, please check your DB".format(str(stop)))

            if len(list_of_stops_to_return) > 0:
                logger.info("Found stops not yet processed, retrying those in the next round")
            return list_of_stops_to_return
        finally:
            self._manager_mutex.release()

    def _start_routemanager(self):
        self._manager_mutex.acquire()
        try:
            if not self._is_started:
                logger.info("Starting routemanager {}", str(self.name))
                stops: List[Location] = self.db_wrapper.stop_from_db_without_quests(
                    self.geofence_helper, self._level)
                logger.info('Detected {} stops without quests', len(stops))
                logger.debug('Detected stops without quests: {}', str(stops))
                self._stoplist: List[Location] = stops

                self._prio_queue = None
                self.delay_after_timestamp_prio = None
                self.starve_route = False
                self._is_started = True
                self._first_round_finished = False
                if not self._first_started:
                    logger.info(
                        "First starting quest route - copying original route for later use")
                    self._routecopy = self._route.copy()
                    self._first_started = True
                else:
                    logger.info("Restoring original route")
                    self._route = self._routecopy.copy()

                for route_location in self._stoplist:
                    if route_location not in self._route:
                        logger.warning("Stop with coords {} seems new and not in route.", str(route_location))

                if len(stops) == 0:
                    logger.info('No unprocessed  Stops detected - quit worker')
                    self._route: List[Location] = []

                if 0 < len(stops) < len(self._route) \
                        and (len(stops)-len(self._route)) * 100 / len(stops) < 80:
                    # Calculating new route because 80 percent of stops are processed
                    logger.info('There are less stops without quest than routepositions - recalc')
                    self._route = list(set(self._route) - (set(self._route) - set(stops)))
                    coords = self._route
                    self._clear_coords()
                    self.add_coords_list(coords)
                    self._overwrite_calculation = True
                    self._recalc_route_workertype()
                else:
                    self._init_route_queue()

                logger.info('Getting {} positions in route', len(self._route))


        finally:
            self._manager_mutex.release()

    def _quit_route(self):
        logger.info('Shutdown Route {}', str(self.name))
        self._is_started = False

    def _check_coords_before_returning(self, lat, lng):
        if self.init:
            logger.info('Init Mode - coord is valid')
            return True
        stop = Location(lat, lng)
        logger.info('Checking Stop with ID {}', str(stop))
        if stop not in self._stoplist and not self._level:
            logger.info('Already got this Stop')
            return False
        logger.info('Getting new Stop')
        return True
