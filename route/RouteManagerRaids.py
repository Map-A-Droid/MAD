import logging
from route.RouteManagerBase import RouteManagerBase

log = logging.getLogger(__name__)


class RouteManagerRaids(RouteManagerBase):
    def __init__(self, db_wrapper, coords, max_radius, max_coords_within_radius, path_to_include_geofence,
                 path_to_exclude_geofence, routefile, mode=None, settings=None, init=False,
                 name="unknown", delay_after_timestamp_prio=None):
        RouteManagerBase.__init__(self, db_wrapper=db_wrapper, coords=coords, max_radius=max_radius,
                                  max_coords_within_radius=max_coords_within_radius,
                                  path_to_include_geofence=path_to_include_geofence,
                                  path_to_exclude_geofence=path_to_exclude_geofence,
                                  routefile=routefile, init=init,
                                  name=name, settings=settings
                                  )
        self.mode = mode

    def _retrieve_latest_priority_queue(self):
        return self.db_wrapper.get_next_raid_hatches(self.delay_after_timestamp_prio,
                                                     self.geofence_helper)

    def _get_coords_post_init(self):
        return self.db_wrapper.gyms_from_db(self.geofence_helper)
