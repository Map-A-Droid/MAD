import collections
import time

from route.RouteManagerBase import RouteManagerBase
from utils.logging import logger

Location = collections.namedtuple('Location', ['lat', 'lng'])


class RouteManagerQuests(RouteManagerBase):
    def generate_stop_list(self):
        self._stoplist = []
        time.sleep(5)
        stops = self.db_wrapper.stop_from_db_without_quests(
            self.geofence_helper)
        logger.info('Detected stops without quests: {}', str(stops))
        for stop in stops:
            self._stoplist.append(str(stop[0]) + '#' + str(stop[1]))
        if len(stops) == 0:
            return []
        return stops

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

    def __init__(self, db_wrapper, coords, max_radius, max_coords_within_radius, path_to_include_geofence,
                 path_to_exclude_geofence, routefile, mode=None, init=False,
                 name="unknown", settings=None):
        RouteManagerBase.__init__(self, db_wrapper=db_wrapper, coords=coords, max_radius=max_radius,
                                  max_coords_within_radius=max_coords_within_radius,
                                  path_to_include_geofence=path_to_include_geofence,
                                  path_to_exclude_geofence=path_to_exclude_geofence,
                                  routefile=routefile, init=init,
                                  name=name, settings=settings, mode=mode
                                  )
        self.starve_route = False
        self._stoplist = []
        self._unprocessed_stops = {}

    def _get_coords_after_finish_route(self):
        self._manager_mutex.acquire()
        try:
            if self._start_calc:
                logger.info("Another process already calculate the new route")
                return True
            self._start_calc = True
            if not self._route_queue.empty():
                self._start_calc = False
                return True
            openstops = self.generate_stop_list()
            if len(openstops) == 0:
                self._start_calc = False
                return False
            coords = self._check_unprocessed_stops(openstops)
            if len(coords) > 0:
                self.clear_coords()
                self.add_coords_list(coords)
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

    def _check_unprocessed_stops(self, openstops):
        self._stoplistunprocessed = []
        if len(openstops) == 0:
            self._unprocessed_stops = {}
        else:
            # Only want open stops - not maybe processed in the last round
            self._unprocessed_stops_new = {}
            for stop in openstops:
                check_stop = str(stop[0]) + '#' + str(stop[1])
                if check_stop not in self._unprocessed_stops:
                    self._unprocessed_stops_new[check_stop] = 1
                else:
                    value = self._unprocessed_stops[check_stop] + 1
                    self._unprocessed_stops_new[check_stop] = value

            # copy back the new list
            self._unprocessed_stops = self._unprocessed_stops_new

        for error_stop in self._unprocessed_stops:
            # generate new location list
            if self._unprocessed_stops[error_stop] < 4:
                logger.warning("Found not processed Stop: {}", str(error_stop))
                stop_split = error_stop.split("#")
                self._stoplistunprocessed.append(
                    [stop_split[0], stop_split[1]])
            else:
                logger.error(
                    "Cannot process stop mit lat-lng {} 3 times - please check your db.", str(error_stop))

        if len(self._stoplistunprocessed) > 0:
            logger.info('Retry some stops')
            return self._stoplistunprocessed
        else:
            logger.info('Dont found unprocessed stops')
            return []

    def _start_routemanager(self):
        self._manager_mutex.acquire()
        try:
            if not self._is_started:
                logger.info("Starting routemanager {}", str(self.name))
                stops = self.db_wrapper.stop_from_db_without_quests(
                    self.geofence_helper)
                logger.info('Detected stops without quests: {}', str(stops))
                for stop in stops:
                    self._stoplist.append(str(stop[0]) + '#' + str(stop[1]))

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
                self._init_route_queue()
        finally:
            self._manager_mutex.release()

    def _quit_route(self):
        logger.info('Shutdown Route {}', str(self.name))
        self._unprocessed_stops = {}
        self._is_started = False

    def _check_coords_before_returning(self, lat, lng):
        if self.init:
            logger.info('Init Mode - coord is valid')
            return True
        check_stop = str(lat) + '#' + str(lng)
        logger.info('Checking Stop with ID {}', str(check_stop))
        if check_stop not in self._stoplist:
            logger.info('Already got this Stop')
            return False
        logger.info('Getting new Stop')
        return True
