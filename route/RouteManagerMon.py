from route.RouteManagerBase import RouteManagerBase
from utils.logging import logger


class RouteManagerMon(RouteManagerBase):
    def _priority_queue_update_interval(self):
        return 180

    def _get_coords_after_finish_route(self):
        self._init_route_queue()
        return True

    def _recalc_route_workertype(self):
        self.recalc_route(self._max_radius, self._max_coords_within_radius, 1, delete_old_route=True,
                          nofile=False)
        self._init_route_queue()

    def __init__(self, db_wrapper, coords, max_radius, max_coords_within_radius, path_to_include_geofence,
                 path_to_exclude_geofence, routefile, mode=None, coords_spawns_known=False, init=False,
                 name="unknown", settings=None):
        RouteManagerBase.__init__(self, db_wrapper=db_wrapper, coords=coords, max_radius=max_radius,
                                  max_coords_within_radius=max_coords_within_radius,
                                  path_to_include_geofence=path_to_include_geofence,
                                  path_to_exclude_geofence=path_to_exclude_geofence,
                                  routefile=routefile, init=init,
                                  name=name, settings=settings, mode=mode
                                  )
        self.coords_spawns_known = coords_spawns_known

    def _retrieve_latest_priority_queue(self):
        return self.db_wrapper.retrieve_next_spawns(self.geofence_helper)

    def _get_coords_post_init(self):
        if self.coords_spawns_known:
            logger.info("Reading known Spawnpoints from DB")
            coords = self.db_wrapper.get_detected_spawns(self.geofence_helper)
        else:
            logger.info("Reading unknown Spawnpoints from DB")
            coords = self.db_wrapper.get_undetected_spawns(
                self.geofence_helper)
        return coords

    def _cluster_priority_queue_criteria(self):
        if self.settings is not None:
            return self.settings.get("priority_queue_clustering_timedelta", 300)
        else:
            return 300

    def _start_routemanager(self):
        self._manager_mutex.acquire()
        try:
            if not self._is_started:
                logger.info("Starting routemanager {}", str(self.name))
                self._start_priority_queue()
                self._is_started = True
                self._init_route_queue()
                self._first_round_finished = False
        finally:
            self._manager_mutex.release()

    def _quit_route(self):
        logger.info('Shutdown Route {}', str(self.name))
        if self._update_prio_queue_thread is not None:
            self._stop_update_thread.set()
            self._update_prio_queue_thread.join()
            self._update_prio_queue_thread = None
            self._stop_update_thread.clear()
        self._is_started = False
        self._round_started_time = None

    def _check_coords_before_returning(self, lat, lng):
        return True
