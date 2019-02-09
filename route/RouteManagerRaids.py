import logging

from route.RouteManagerBase import RouteManagerBase

log = logging.getLogger(__name__)


class RouteManagerRaids(RouteManagerBase):
    def _priority_queue_update_interval(self):
        return 300

    def __init__(self, db_wrapper, coords, max_radius, max_coords_within_radius, path_to_include_geofence,
                 path_to_exclude_geofence, routefile, mode=None, settings=None, init=False,
                 name="unknown"):
        RouteManagerBase.__init__(self, db_wrapper=db_wrapper, coords=coords, max_radius=max_radius,
                                  max_coords_within_radius=max_coords_within_radius,
                                  path_to_include_geofence=path_to_include_geofence,
                                  path_to_exclude_geofence=path_to_exclude_geofence,
                                  routefile=routefile, init=init,
                                  name=name, settings=settings, mode=mode
                                  )

    def _retrieve_latest_priority_queue(self):
        # TODO: pass timedelta for timeleft on raids that can be ignored.
        # e.g.: a raid only has 5mins to go, ignore those
        return self.db_wrapper.get_next_raid_hatches(self.delay_after_timestamp_prio,
                                                     self.geofence_helper)

    def _get_coords_post_init(self):
        return self.db_wrapper.gyms_from_db(self.geofence_helper)

    def _cluster_priority_queue_criteria(self):
        if self.settings is not None:
            return self.settings.get("priority_queue_clustering_timedelta", 600)
        else:
            return 600
