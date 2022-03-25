from typing import List, Optional

from loguru import logger

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.model import SettingsRoutecalc, SettingsAreaInitMitm
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.route.RouteManagerBase import RouteManagerBase
from mapadroid.route.prioq.strategy.RaidSpawnPrioStrategy import RaidSpawnPrioStrategy
from mapadroid.utils.collections import Location
from mapadroid.utils.s2Helper import S2Helper
from mapadroid.worker.WorkerType import WorkerType


class RouteManagerInit(RouteManagerBase):
    def __init__(self, db_wrapper: DbWrapper, area: SettingsAreaInitMitm, coords, max_radius, max_coords_within_radius,
                 geofence_helper: GeofenceHelper, routecalc: SettingsRoutecalc,
                 use_s2: bool = False, s2_level: int = 15, mon_ids_iv: Optional[List[int]] = None):

        strategy: Optional[RaidSpawnPrioStrategy] = None
        if False:
            # TODO: Mon Despawn targetted "learning"?
            strategy: RaidSpawnPrioStrategy = RaidSpawnPrioStrategy(clustering_timedelta=clustering_timedelta,
                                                                    clustering_count_per_circle=max_coords_within_radius,
                                                                    clustering_distance=max_radius,
                                                                    db_wrapper=db_wrapper,
                                                                    max_backlog_duration=self.remove_from_queue_backlog,
                                                                    geofence_helper=geofence_helper,
                                                                    delay_after_event=self.delay_after_timestamp_prio)
        RouteManagerBase.__init__(self, db_wrapper=db_wrapper, area=area, coords=coords,
                                  max_radius=max_radius,
                                  max_coords_within_radius=max_coords_within_radius,
                                  geofence_helper=geofence_helper,
                                  routecalc=routecalc, use_s2=use_s2, s2_level=s2_level,
                                  mon_ids_iv=mon_ids_iv,
                                  initial_prioq_strategy=strategy)
        self._settings: SettingsAreaInitMitm = area
        self.init_mode_rounds: int = area.init_mode_rounds if area.init_mode_rounds else 1

    async def _get_coords_after_finish_route(self):
        self._init_route_queue()
        return True

    async def _recalc_route_workertype(self):
        await self.recalc_route(self._max_radius, self._max_coords_within_radius, 1, delete_old_route=True,
                                in_memory=False)
        self._init_route_queue()

    def _delete_coord_after_fetch(self) -> bool:
        return False

    async def _get_coords_fresh(self) -> List[Location]:
        return S2Helper.generate_locations(self.get_max_radius(), self.get_geofence_helper())

    async def start_routemanager(self):
        async with self._manager_mutex:
            if not self._is_started:
                self._is_started = True
                logger.info("Starting routemanager")
                if self._mode != WorkerType.IDLE:
                    await self._start_priority_queue()
                    await self._start_check_routepools()
                    self._init_route_queue()
        return True

    def _quit_route(self):
        logger.info("Shutdown Route")
        self._is_started = False
        self._round_started_time = None

    def _check_coords_before_returning(self, lat, lng, origin):
        return True

    async def _change_init_mapping(self) -> None:
        async with self.db_wrapper as session, session:
            self._settings.init = False
            # TODO: Add or merge? Or first fetch the data? Or just toggle using the helper?
            # TODO: Ensure that even works with SQLAlchemy's functionality in regards to objects and sessions etc...
            try:
                session.add(self._settings)
                await session.commit()
            except Exception as e:
                logger.warning("Failed changing init to False: {}", e)
