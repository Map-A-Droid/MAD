from typing import List, Optional, Tuple

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.helper.TrsSpawnHelper import TrsSpawnHelper
from mapadroid.db.model import SettingsAreaMonMitm, SettingsRoutecalc
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.route.RouteManagerBase import RouteManagerBase
from mapadroid.utils.collections import Location
from mapadroid.utils.logging import LoggerEnums, get_logger

logger = get_logger(LoggerEnums.routemanager)


class RouteManagerMon(RouteManagerBase):
    def __init__(self, db_wrapper: DbWrapper, area: SettingsAreaMonMitm, coords: Optional[List[Location]],
                 max_radius: int, max_coords_within_radius: int,
                 geofence_helper: GeofenceHelper, routecalc: SettingsRoutecalc,
                 use_s2: bool = False, s2_level: int = 15,
                 joinqueue=None, mon_ids_iv: Optional[List[int]] = None):
        RouteManagerBase.__init__(self, db_wrapper=db_wrapper, area=area, coords=coords,
                                  max_radius=max_radius,
                                  max_coords_within_radius=max_coords_within_radius,
                                  geofence_helper=geofence_helper, joinqueue=joinqueue,
                                  use_s2=use_s2, s2_level=s2_level, routecalc=routecalc,
                                  mon_ids_iv=mon_ids_iv
                                  )
        self._settings: SettingsAreaMonMitm = area
        self.coords_spawns_known = area.coords_spawns_known
        self.include_event_id = area.include_event_id
        self.init = area.init
        self.remove_from_queue_backlog = area.remove_from_queue_backlog
        self.delay_after_timestamp_prio = area.delay_after_prio_event
        self.starve_route = area.starve_route
        self._max_clustering = area.max_clustering
        self.init_mode_rounds = area.init_mode_rounds

    def _priority_queue_update_interval(self):
        return 600

    async def _get_coords_after_finish_route(self) -> bool:
        self._init_route_queue()
        return True

    async def _recalc_route_workertype(self):
        await self.recalc_route(self._max_radius, self._max_coords_within_radius, 1, delete_old_route=True,
                          in_memory=False)
        self._init_route_queue()

    async def _retrieve_latest_priority_queue(self) -> List[Tuple[int, Location]]:
        async with self.db_wrapper as session, session:
            return await TrsSpawnHelper.get_next_spawns(session, self.geofence_helper, self.include_event_id)

    async def _get_coords_post_init(self):
        async with self.db_wrapper as session, session:
            if self.coords_spawns_known:
                self.logger.info("Reading known Spawnpoints from DB")
                coords = await TrsSpawnHelper.get_known_of_area(session, self.geofence_helper, self.include_event_id)
            else:
                self.logger.info("Reading unknown Spawnpoints from DB")
                coords = await TrsSpawnHelper.get_known_without_despawn_of_area(session, self.geofence_helper,
                                                                                self.include_event_id)
        self._start_priority_queue()
        return coords

    def _cluster_priority_queue_criteria(self):
        return self._settings.priority_queue_clustering_timedelta

    async def _start_routemanager(self):
        with self._manager_mutex:
            if not self._is_started:
                self._is_started = True
                self.logger.info("Starting routemanager {}", self.name)
                if not self.init:
                    self._start_priority_queue()
                await self._start_check_routepools()
                self._init_route_queue()
        return True

    def _delete_coord_after_fetch(self) -> bool:
        return False

    def _quit_route(self):
        self.logger.info('Shutdown Route {}', self.name)
        self._is_started = False
        self._round_started_time = None

    def _check_coords_before_returning(self, lat, lng, origin):
        return True

    async def _change_init_mapping(self) -> None:
        async with self.db_wrapper as session, session:
            self._settings.init = False
            # TODO: Add or merge? Or first fetch the data? Or just toggle using the helper?
            # TODO: Ensure that even works with SQLAlchemy's functionality in regards to objects and sessions etc...
            await session.merge(self._settings)
