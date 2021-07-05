from typing import List, Optional, Tuple

from loguru import logger

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.helper.TrsSpawnHelper import TrsSpawnHelper
from mapadroid.db.model import SettingsAreaMonMitm, SettingsRoutecalc
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.route.RouteManagerBase import RouteManagerBase
from mapadroid.utils.collections import Location


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
        self.coords_spawns_known: bool = True if area.coords_spawns_known == 1 else False
        self.include_event_id: Optional[int] = area.include_event_id
        self.init: bool = True if area.init == 1 else False
        self.remove_from_queue_backlog: Optional[int] = int(
            area.remove_from_queue_backlog) if area.remove_from_queue_backlog else None
        self.delay_after_timestamp_prio: Optional[int] = area.delay_after_prio_event
        self.starve_route: bool = True if area.starve_route == 1 else False
        if area.max_clustering:
            self._max_clustering: int = area.max_clustering
        self.init_mode_rounds: int = area.init_mode_rounds if area.init_mode_rounds else 1

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

    async def _get_coords_post_init(self) -> List[Location]:
        async with self.db_wrapper as session, session:
            if self.coords_spawns_known:
                logger.info("Reading known Spawnpoints from DB")
                spawns = await TrsSpawnHelper.get_known_of_area(session, self.geofence_helper, self.include_event_id)
            else:
                logger.info("Reading unknown Spawnpoints from DB")
                spawns = await TrsSpawnHelper.get_known_without_despawn_of_area(session, self.geofence_helper,
                                                                                self.include_event_id)
        coords: List[Location] = []
        for spawn in spawns:
            coords.append(Location(spawn.latitude, spawn.longitude))
        await self._start_priority_queue()
        return coords

    def _cluster_priority_queue_criteria(self):
        return self._settings.priority_queue_clustering_timedelta

    async def start_routemanager(self):
        async with self._manager_mutex:
            if not self._is_started:
                self._is_started = True
                logger.info("Starting routemanager {}", self.name)
                if not self.init:
                    await self._start_priority_queue()
                await self._start_check_routepools()
                self._init_route_queue()
        return True

    def _delete_coord_after_fetch(self) -> bool:
        return False

    def _quit_route(self):
        logger.info('Shutdown Route {}', self.name)
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
