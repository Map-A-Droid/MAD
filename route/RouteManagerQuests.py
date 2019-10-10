import collections
import time
from typing import List
from db.dbWrapperBase import DbWrapperBase
from route.RouteManagerBase import RouteManagerBase
from utils.logging import logger

Location = collections.namedtuple('Location', ['lat', 'lng'])


class RouteManagerQuests(RouteManagerBase):
    def generate_stop_list(self):
        time.sleep(5)
        stops = self.db_wrapper.stop_from_db_without_quests(
            self.geofence_helper, self._level)
        logger.info('Detected stops without quests: {}', str(len(stops)))
        logger.debug('Detected stops without quests: {}', str(stops))
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
                 level: bool = False, calctype: str = "optimized", joinqueue = None):
        RouteManagerBase.__init__(self, db_wrapper=db_wrapper, coords=coords, max_radius=max_radius,
                                  max_coords_within_radius=max_coords_within_radius,
                                  path_to_include_geofence=path_to_include_geofence,
                                  path_to_exclude_geofence=path_to_exclude_geofence,
                                  routefile=routefile, init=init,
                                  name=name, settings=settings, mode=mode, level=level, calctype=calctype,
                                  joinqueue=joinqueue
                                  )
        self.starve_route = False
        self._stoplist: List[Location] = []

        self._shutdown_route: bool = False
        self._routecopy: List[Location] = []
        self._tempinit: bool = False

    def _get_coords_after_finish_route(self) -> bool:
        if self._level:
            logger.info("Level Mode - switch to next area")
            return False
        self._manager_mutex.acquire()
        try:

            if self._shutdown_route:
                logger.info('Other worker shutdown route {} - leaving it', str(self.name))
                return False

            if self._start_calc:
                logger.info("Another process already calculate the new route")
                return True
            self._start_calc = True
            self.generate_stop_list()
            if len(self._stoplist) == 0:
                logger.info("Dont getting new stops - leaving now.")
                self._shutdown_route = True
                self._restore_original_route()
                self._start_calc = False
                return False
            coords: List[Location] = self._check_unprocessed_stops()
            # remove coords to be ignored from coords
            coords = [coord for coord in coords if coord not in self._coords_to_be_ignored]
            if len(coords) > 0:
                logger.info("Getting new coords - recalc quick route")
                self._recalc_stop_route(coords)
                self._start_calc = False
            else:
                logger.info("Dont getting new stops - leaving now.")
                self._shutdown_route = True
                self._start_calc = False
                self._restore_original_route()
                return False
            return True
        finally:
            self._manager_mutex.release()

    def _restore_original_route(self):
        if not self._tempinit:
            logger.info("Restoring original route")
            self._route = self._routecopy.copy()

    def _check_unprocessed_stops(self):
        self._manager_mutex.acquire()

        try:
            list_of_stops_to_return: List[Location] = []

            if len(self._stoplist) == 0:
                return list_of_stops_to_return
            else:
                # we only want to add stops that we haven't spun yet
                for stop in self._stoplist:
                    if stop not in self._stops_not_processed:
                        self._stops_not_processed[stop] = 1
                    else:
                        self._stops_not_processed[stop] += 1

            for stop, error_count in self._stops_not_processed.items():
                if stop not in self._stoplist:
                    logger.info("Location {} is no longer in our stoplist and will be ignored".format(str(stop)))
                    self._coords_to_be_ignored.add(stop)
                elif error_count < 4:
                    logger.warning("Found stop not processed yet: {}".format(str(stop)))
                    list_of_stops_to_return.append(stop)
                else:
                    logger.error("Stop {} has not been processed thrice in a row, "
                                 "please check your DB".format(str(stop)))
                    self._coords_to_be_ignored.add(stop)

            if len(list_of_stops_to_return) > 0:
                logger.info("Found stops not yet processed, retrying those in the next round")
            return list_of_stops_to_return
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

                if self.init:
                    logger.info('Starting init mode')
                    self._init_route_queue()
                    self._tempinit = True
                    return True

                if not self._first_started:
                    logger.info(
                        "First starting quest route - copying original route {} for later use", str(self.name))
                    self._routecopy = self._route.copy()
                    self._first_started = True
                else:
                    logger.info("Restoring original route {} ", str(self.name))
                    self._route = self._routecopy.copy()

                new_stops = list(set(stops) - set(self._route))
                if len(new_stops) > 0:
                    for stop in new_stops:
                        logger.warning("Stop with coords {} seems new and not in route.", str(stop))

                if len(stops) == 0:
                    logger.info('No unprocessed Stops detected in route {} - quit worker', str(self.name))
                    self._shutdown_route = True
                    self._restore_original_route()
                    self._route: List[Location] = []
                    return False

                if 0 < len(stops) < len(self._route) \
                        and len(stops)/len(self._route) <= 0.3:
                    # Calculating new route because 70 percent of stops are processed
                    logger.info('There are less stops without quest than routepositions - recalc')
                    self._recalc_stop_route(stops)
                elif len(self._route) == 0 and len(stops) > 0:
                    logger.warning("Something wrong with area {}: it have many new stops - better delete routefile!",
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
        return True

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

    def _check_coords_before_returning(self, lat, lng):
        if self.init:
            logger.debug('Init Mode - coord is valid')
            return True
        stop = Location(lat, lng)
        logger.info('Checking Stop with ID {}', str(stop))
        if stop not in self._stoplist and not self._level:
            logger.info('Already got this Stop')
            return False
        logger.info('Getting new Stop')
        return True
