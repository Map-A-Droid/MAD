from route.RouteManagerBase import RouteManagerBase
from utils.logging import logger


class RouteManagerRaids(RouteManagerBase):
    def _priority_queue_update_interval(self):
        return 300

    def _get_coords_after_finish_route(self):
        self._init_route_queue()
        self.get_worker_workerpool()
        return True

    def _recalc_route_workertype(self):
        self.recalc_route(self._max_radius, self._max_coords_within_radius, 1, delete_old_route=True,
                          nofile=False)
        self._init_route_queue()

    def __init__(self, db_wrapper, coords, max_radius, max_coords_within_radius, path_to_include_geofence,
                 path_to_exclude_geofence, routefile, mode=None, settings=None, init=False,
                 name="unknown", joinqueue=None):
        RouteManagerBase.__init__(self, db_wrapper=db_wrapper, coords=coords, max_radius=max_radius,
                                  max_coords_within_radius=max_coords_within_radius,
                                  path_to_include_geofence=path_to_include_geofence,
                                  path_to_exclude_geofence=path_to_exclude_geofence,
                                  routefile=routefile, init=init,
                                  name=name, settings=settings, mode=mode, joinqueue=joinqueue
                                  )

    def _retrieve_latest_priority_queue(self):
        # TODO: pass timedelta for timeleft on raids that can be ignored.
        # e.g.: a raid only has 5mins to go, ignore those
        return self.db_wrapper.get_next_raid_hatches(self.delay_after_timestamp_prio,
                                                     self.geofence_helper)

    def _delete_coord_after_fetch(self) -> bool:
        return False

    def _get_coords_post_init(self):
        return self.db_wrapper.gyms_from_db(self.geofence_helper)

    def _cluster_priority_queue_criteria(self):
        if self.settings is not None:
            return self.settings.get("priority_queue_clustering_timedelta", 600)
        else:
            return 600

    def _start_routemanager(self):
        self._manager_mutex.acquire()
        try:
            if not self._is_started:
                self._is_started = True
                logger.info("Starting routemanager {}", str(self.name))
                if self.mode != "idle":
                    self._start_priority_queue()
                    self._start_check_routepools()
                    self._init_route_queue()

                self._first_round_finished = False
        finally:
            self._manager_mutex.release()

        return True

    def _quit_route(self):
        logger.info("Shutdown Route {}", str(self.name))
        self._is_started = False
        self._round_started_time = None

    def _check_coords_before_returning(self, lat, lng):
        return True
