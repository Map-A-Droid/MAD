import logging

from route.RouteManagerBase import RouteManagerBase

log = logging.getLogger(__name__)


class RouteManagerIV(RouteManagerBase):
    def _priority_queue_update_interval(self):
        return 60

    def _retrieve_latest_priority_queue(self):
        # IV is excluded from clustering, check RouteManagerBase for more info
        latest_priorities = self.db_wrapper.get_to_be_encountered(geofence_helper=self.geofence_helper,
                                                                  min_time_left_seconds=self.settings.get(
                                                                      "min_time_left_seconds", None),
                                                                  eligible_mon_ids=self.settings.get("mon_ids_iv", None))
        # extract the encounterIDs and set them in the routeManager...
        new_list = []
        for prio in latest_priorities:
            new_list.append(prio[2])
        self.encounter_ids_left = new_list
        return latest_priorities

    def _get_coords_post_init(self):
        # not necessary
        pass

    def _cluster_priority_queue_criteria(self):
        # clustering is of no use for now
        pass

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
        self.encounter_ids_left = []
        self.starve_route = True
        if self.delay_after_timestamp_prio is None:
            # just set a value to enable the queue
            self.delay_after_timestamp_prio = 5
