from mapadroid.route.RouteManagerBase import RouteManagerBase
from mapadroid.utils.logging import get_logger, LoggerEnums


logger = get_logger(LoggerEnums.routemanager)


class RouteManagerRaids(RouteManagerBase):
    def __init__(self, db_wrapper, dbm, area_id, coords, max_radius, max_coords_within_radius,
                 path_to_include_geofence,
                 path_to_exclude_geofence, routefile, mode=None, settings=None, init=False,
                 name="unknown", joinqueue=None, use_s2: bool = False, s2_level: int = 15):
        RouteManagerBase.__init__(self, db_wrapper=db_wrapper, dbm=dbm, area_id=area_id, coords=coords,
                                  max_radius=max_radius,
                                  max_coords_within_radius=max_coords_within_radius,
                                  path_to_include_geofence=path_to_include_geofence,
                                  path_to_exclude_geofence=path_to_exclude_geofence,
                                  routefile=routefile, init=init,
                                  name=name, settings=settings, mode=mode, use_s2=True, s2_level=s2_level,
                                  joinqueue=joinqueue
                                  )

    def _priority_queue_update_interval(self):
        return 300

    def _get_coords_after_finish_route(self):
        self._init_route_queue()
        return True

    def _recalc_route_workertype(self):
        self.recalc_route(self._max_radius, self._max_coords_within_radius, 1, delete_old_route=True,
                          in_memory=False)
        self._init_route_queue()

    def _retrieve_latest_priority_queue(self):
        # TODO: pass timedelta for timeleft on raids that can be ignored.
        # e.g.: a raid only has 5mins to go, ignore those
        return self.db_wrapper.get_next_raid_hatches(self.delay_after_timestamp_prio,
                                                     self.geofence_helper)

    def _delete_coord_after_fetch(self) -> bool:
        return False

    def _get_coords_post_init(self):
        coords = self.db_wrapper.gyms_from_db(self.geofence_helper)
        including_stops = self._data_manager.get_resource('area', self.area_id).get('including_stops', False)
        if including_stops:
            self.logger.info("Include stops in coords list too!")
            coords.extend(self.db_wrapper.stops_from_db(self.geofence_helper))

        return coords

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
                self.logger.info("Starting routemanager")
                if self.mode != "idle":
                    self._start_priority_queue()
                    self._start_check_routepools()
                    self._init_route_queue()
        finally:
            self._manager_mutex.release()

        return True

    def _quit_route(self):
        self.logger.info("Shutdown Route")
        self._is_started = False
        self._round_started_time = None

    def _check_coords_before_returning(self, lat, lng, origin):
        return True
