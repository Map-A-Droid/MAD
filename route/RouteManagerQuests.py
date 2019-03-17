import logging
from route.RouteManagerBase import RouteManagerBase

log = logging.getLogger(__name__)


class RouteManagerQuests(RouteManagerBase):
    def _accept_empty_route(self):
        return False

    def generate_stop_list(self):
        self._stoplist = []
        stops = self.db_wrapper.stop_from_db_without_quests(self.geofence_helper)
        log.info('Detected stops without quests: %s' % str(stops))
        for stop in stops:
            self._stoplist.append(str(stop[0]) + '-' + str(stop[1]))
            if len(stops) == 0:
                return []
        return stops

    def _retrieve_latest_priority_queue(self):
        return None

    def _get_coords_post_init(self):
        return self.generate_stop_list()

    def _cluster_priority_queue_criteria(self):
        pass

    def _priority_queue_update_interval(self):
        return 0

    def _recalc_route_workertype(self, del_route_file=False):
        self.recalc_route(self._max_radius, self._max_coords_within_radius, 1, delete_old_route=del_route_file,
                          nofile=True)

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

    def _get_coords_after_finish_route(self):
        return self.generate_stop_list()

    def _start_routemanager(self):
        self._manager_mutex.acquire()
        try:
            if not self._is_started:
                log.info("Starting routemanager %s" % str(self.name))
                stops = self.db_wrapper.stop_from_db_without_quests(self.geofence_helper)
                log.info('Detected stops without quests: %s' % str(stops))
                for stop in stops:
                    self._stoplist.append(str(stop[0]) + '-' + str(stop[1]))
                self._prio_queue = None
                self.delay_after_timestamp_prio = None
                self.starve_route = False
                self._is_started = True
        finally:
            self._manager_mutex.release()

    def _quit_route(self):
        log.info('Shutdown Route %s' % str(self.name))
        self._is_started = False

    def _check_coords_before_returning(self, lat, lng):
        if self.init:
            log.info('Init Mode - coord is valid')
            return True
        check_stop = str(lat) + '-' + str(lng)
        log.info('Checking Stop with ID %s' % str(check_stop))
        if check_stop not in self._stoplist:
            log.info('Already got this Stop')
            return False
        log.info('Getting new Stop')
        return True

