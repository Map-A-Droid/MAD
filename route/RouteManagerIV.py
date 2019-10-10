import heapq
from typing import List

from route.RouteManagerBase import RouteManagerBase
from utils.logging import logger


class RouteManagerIV(RouteManagerBase):
    def _priority_queue_update_interval(self):
        return 60

    def _get_coords_after_finish_route(self) -> bool:
        return True

    def _recalc_route_workertype(self):
        self.recalc_route(self._max_radius, self._max_coords_within_radius, 1, delete_old_route=False,
                          nofile=False)

    def _retrieve_latest_priority_queue(self):
        # IV is excluded from clustering, check RouteManagerBase for more info
        latest_priorities = self.db_wrapper.get_to_be_encountered(geofence_helper=self.geofence_helper,
                                                                  min_time_left_seconds=self.settings.get(
                                                                      "min_time_left_seconds", None),
                                                                  eligible_mon_ids=
                                                                  self.settings.get("mon_ids_iv_raw", None))
        # extract the encounterIDs and set them in the routeManager...
        new_list = []
        for prio in latest_priorities:
            new_list.append(prio[2])
        self.encounter_ids_left = new_list

        self._manager_mutex.acquire()
        heapq.heapify(latest_priorities)
        self._prio_queue = latest_priorities
        self._manager_mutex.release()
        return None
        # return latest_priorities

    def get_encounter_ids_left(self) -> List[int]:
        return self.encounter_ids_left

    def _get_coords_post_init(self):
        # not necessary
        pass

    def _cluster_priority_queue_criteria(self):
        # clustering is of no use for now
        pass

    def __init__(self, db_wrapper, coords, max_radius, max_coords_within_radius, path_to_include_geofence,
                 path_to_exclude_geofence, routefile, mode=None, init=False,
                 name="unknown", settings=None, joinqueue=None):
        RouteManagerBase.__init__(self, db_wrapper=db_wrapper, coords=coords, max_radius=max_radius,
                                  max_coords_within_radius=max_coords_within_radius,
                                  path_to_include_geofence=path_to_include_geofence,
                                  path_to_exclude_geofence=path_to_exclude_geofence,
                                  routefile=routefile, init=init,
                                  name=name, settings=settings, mode=mode, joinqueue=joinqueue
                                  )
        self.encounter_ids_left: List[int] = []
        self.starve_route = True
        if self.delay_after_timestamp_prio is None:
            # just set a value to enable the queue
            self.delay_after_timestamp_prio = 5

    def _delete_coord_after_fetch(self) -> bool:
        return False

    def _start_routemanager(self):
        self._manager_mutex.acquire()
        try:
            if not self._is_started:
                self._is_started = True
                logger.info("Starting routemanager {}", str(self.name))
                self._start_priority_queue()
        finally:
            self._manager_mutex.release()
        return True

    def _quit_route(self):
        logger.info('Shutdown Route {}', str(self.name))
        self._is_started = False
        self._round_started_time = None

    def _check_coords_before_returning(self, lat, lng):
        return True
