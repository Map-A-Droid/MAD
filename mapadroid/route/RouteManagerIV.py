from typing import List, Optional, Set

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.helper.PokemonHelper import PokemonHelper
from mapadroid.db.model import SettingsAreaIvMitm, SettingsRoutecalc
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.route.RouteManagerBase import RouteManagerBase
from mapadroid.route.prioq.strategy.IvOnlyPrioStrategy import IvOnlyPrioStrategy
from mapadroid.utils.collections import Location
from mapadroid.utils.logging import LoggerEnums, get_logger

logger = get_logger(LoggerEnums.routemanager)


class RouteManagerIV(RouteManagerBase):
    def __init__(self, db_wrapper: DbWrapper, area: SettingsAreaIvMitm, coords: Optional[List[Location]],
                 max_radius: int, max_coords_within_radius: int,
                 geofence_helper: GeofenceHelper, routecalc: SettingsRoutecalc,
                 mon_ids_iv: Optional[List[int]] = None):
        self.delay_after_timestamp_prio: Optional[int] = area.delay_after_prio_event
        if self.delay_after_timestamp_prio is None or self.delay_after_timestamp_prio == 0:
            # just set a value to enable the queue
            self.delay_after_timestamp_prio = 10
        iv_strategy: IvOnlyPrioStrategy = IvOnlyPrioStrategy(clustering_timedelta=120,
                                                             clustering_count_per_circle=max_coords_within_radius,
                                                             clustering_distance=max_radius,
                                                             max_backlog_duration=area.remove_from_queue_backlog,
                                                             db_wrapper=db_wrapper,
                                                             geofence_helper=geofence_helper,
                                                             min_time_left_seconds=area.min_time_left_seconds,
                                                             mon_ids_to_scan=mon_ids_iv,
                                                             delay_after_event=self.delay_after_timestamp_prio)
        RouteManagerBase.__init__(self, db_wrapper=db_wrapper, area=area, coords=coords,
                                  max_radius=max_radius,
                                  max_coords_within_radius=max_coords_within_radius,
                                  geofence_helper=geofence_helper,
                                  routecalc=routecalc, mon_ids_iv=mon_ids_iv,
                                  initial_prioq_strategy=iv_strategy)
        self._settings: SettingsAreaIvMitm = area
        self.encounter_ids_left: List[int] = []
        self.starve_route: bool = True
        self.remove_from_queue_backlog: int = area.remove_from_queue_backlog

    def _priority_queue_update_interval(self):
        return 60

    async def _any_coords_left_after_finishing_route(self) -> bool:
        return True

    async def _recalc_route_workertype(self):
        await self.recalc_route(self._max_radius, self._max_coords_within_radius, 1, delete_old_route=False,
                                in_memory=False)

    async def _retrieve_latest_priority_queue(self):
        # IV is excluded from clustering, check RouteManagerBase for more info
        async with self.db_wrapper as session, session:
            latest_priorities = await PokemonHelper.get_to_be_encountered(session,
                                                                          geofence_helper=self.geofence_helper,
                                                                          min_time_left_seconds=self._settings.min_time_left_seconds,
                                                                          eligible_mon_ids=self._mon_ids_iv)
        # extract the encounterIDs and set them in the routeManager...
        new_list: Set = set()
        # TODO: Adjust for new prioQ stuff...
        for prio in latest_priorities:
            new_list.add(prio[2])
        self.encounter_ids_left = list(new_list)
        # Clear old encounters in the list...
        return latest_priorities

    def get_encounter_ids_left(self) -> List[int]:
        return self.encounter_ids_left

    async def _get_coords_fresh(self, dynamic: bool) -> List[Location]:
        # not necessary
        pass

    def _cluster_priority_queue_criteria(self):
        # clustering is of no use for now
        pass

    def _delete_coord_after_fetch(self) -> bool:
        return False

    async def start_routemanager(self):
        async with self._manager_mutex:
            if not self._is_started:
                self._is_started = True
                logger.info("Starting routemanager")
                await self._start_priority_queue()
        return True

    async def _quit_route(self):
        logger.info('Shutdown Route')
        self._is_started = False
        self._round_started_time = None

    def _check_coords_before_returning(self, lat, lng, origin):
        return True

    def _remove_deprecated_prio_events(self) -> bool:
        return False

    def _can_pass_prioq_coords(self) -> bool:
        # Override the base class. No need to pass prioq coords.
        return False

    def _may_update_routepool(self):
        return False
