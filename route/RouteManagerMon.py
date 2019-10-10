from route.RouteManagerBase import RouteManagerBase
from utils.logging import logger


class RouteManagerMon(RouteManagerBase):
    def _priority_queue_update_interval(self):
        return 180

    def _get_coords_after_finish_route(self) -> bool:
        self._init_route_queue()
        return True

    def _recalc_route_workertype(self):
        self.recalc_route(self._max_radius, self._max_coords_within_radius, 1, delete_old_route=True,
                          nofile=False)
        self._init_route_queue()

    def __init__(self, db_wrapper, coords, max_radius, max_coords_within_radius, path_to_include_geofence,
                 path_to_exclude_geofence, routefile, mode=None, coords_spawns_known=False, init=False,
                 name="unknown", settings=None, joinqueue=None):
        RouteManagerBase.__init__(self, db_wrapper=db_wrapper, coords=coords, max_radius=max_radius,
                                  max_coords_within_radius=max_coords_within_radius,
                                  path_to_include_geofence=path_to_include_geofence,
                                  path_to_exclude_geofence=path_to_exclude_geofence,
                                  routefile=routefile, init=init,
                                  name=name, settings=settings, mode=mode, joinqueue=joinqueue
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
        self._start_priority_queue()
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
                self._is_started = True
                logger.info("Starting routemanager {}", str(self.name))
                if not self.init: self._start_priority_queue()
                self._start_check_routepools()
                self._init_route_queue()
                self._first_round_finished = False
        finally:
            self._manager_mutex.release()
        return True

    def _delete_coord_after_fetch(self) -> bool:
        return False

    def _quit_route(self):
        logger.info('Shutdown Route {}', str(self.name))
        self._is_started = False
        self._round_started_time = None

    def _check_coords_before_returning(self, lat, lng):
        return True
