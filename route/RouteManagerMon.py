import logging

from route.RouteManagerBase import RouteManagerBase

log = logging.getLogger(__name__)


class RouteManagerMon(RouteManagerBase):
    def _priority_queue_update_interval(self):
        return 180

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
            log.info("Reading known Spawnpoints from DB")
            coords = self.db_wrapper.get_detected_spawns(self.geofence_helper)
        else:
            log.info("Reading unknown Spawnpoints from DB")
            coords = self.db_wrapper.get_undetected_spawns(
                self.geofence_helper)
        return coords

    def _cluster_priority_queue_criteria(self):
        if self.settings is not None:
            return self.settings.get("priority_queue_clustering_timedelta", 300)
        else:
            return 300
