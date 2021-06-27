from typing import List, Optional

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.helper.GymHelper import GymHelper
from mapadroid.db.helper.PokestopHelper import PokestopHelper
from mapadroid.db.helper.RaidHelper import RaidHelper
from mapadroid.db.model import SettingsAreaRaidsMitm, SettingsRoutecalc
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.route.RouteManagerBase import RouteManagerBase
from mapadroid.utils.collections import Location
from mapadroid.utils.logging import LoggerEnums, get_logger
from mapadroid.worker.WorkerType import WorkerType

logger = get_logger(LoggerEnums.routemanager)


class RouteManagerRaids(RouteManagerBase):
    def __init__(self, db_wrapper: DbWrapper, area: SettingsAreaRaidsMitm, coords, max_radius, max_coords_within_radius,
                 geofence_helper: GeofenceHelper, routecalc: SettingsRoutecalc,
                 joinqueue=None, use_s2: bool = False, s2_level: int = 15, mon_ids_iv: Optional[List[int]] = None):
        RouteManagerBase.__init__(self, db_wrapper=db_wrapper, area=area, coords=coords,
                                  max_radius=max_radius,
                                  max_coords_within_radius=max_coords_within_radius,
                                  geofence_helper=geofence_helper,
                                  routecalc=routecalc, use_s2=use_s2, s2_level=s2_level,
                                  joinqueue=joinqueue, mon_ids_iv=mon_ids_iv
                                  )
        self._settings: SettingsAreaRaidsMitm = area
        self.remove_from_queue_backlog: Optional[int] = int(
            area.remove_from_queue_backlog) if area.remove_from_queue_backlog else None
        self.delay_after_timestamp_prio: Optional[int] = area.delay_after_prio_event
        self.starve_route: bool = True if area.starve_route == 1 else False
        self.init_mode_rounds: int = area.init_mode_rounds
        self.init: bool = True if area.init == 1 else False

    def _priority_queue_update_interval(self):
        return 300

    async def _get_coords_after_finish_route(self):
        self._init_route_queue()
        return True

    async def _recalc_route_workertype(self):
        await self.recalc_route(self._max_radius, self._max_coords_within_radius, 1, delete_old_route=True,
                          in_memory=False)
        self._init_route_queue()

    async def _retrieve_latest_priority_queue(self):
        # TODO: pass timedelta for timeleft on raids that can be ignored.
        # e.g.: a raid only has 5mins to go, ignore those
        async with self.db_wrapper as session, session:
            return await RaidHelper.get_next_hatches(session, self.geofence_helper)

    def _delete_coord_after_fetch(self) -> bool:
        return False

    async def _get_coords_post_init(self) -> List[Location]:
        async with self.db_wrapper as session, session:
            coords: List[Location] = await GymHelper.get_locations_in_fence(session, self.geofence_helper)
            if self._settings.including_stops:
                logger.info("Include stops in coords list too!")
                coords.extend(await PokestopHelper.get_locations_in_fence(session, self.geofence_helper))

        return coords

    def _cluster_priority_queue_criteria(self) -> float:
        return self._settings.priority_queue_clustering_timedelta \
            if self._settings.priority_queue_clustering_timedelta is not None else 600

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
            await session.merge(self._settings)
