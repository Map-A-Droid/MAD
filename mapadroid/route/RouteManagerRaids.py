from typing import List, Optional

from loguru import logger

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.helper.GymHelper import GymHelper
from mapadroid.db.helper.PokestopHelper import PokestopHelper
from mapadroid.db.model import SettingsAreaRaidsMitm, SettingsRoutecalc
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.route.RouteManagerBase import RouteManagerBase
from mapadroid.route.SubrouteReplacingMixin import SubrouteReplacingMixin
from mapadroid.route.prioq.strategy.RaidSpawnPrioStrategy import RaidSpawnPrioStrategy
from mapadroid.utils.collections import Location


class RouteManagerRaids(SubrouteReplacingMixin, RouteManagerBase):
    def __init__(self, db_wrapper: DbWrapper, area: SettingsAreaRaidsMitm, coords, max_radius, max_coords_within_radius,
                 geofence_helper: GeofenceHelper, routecalc: SettingsRoutecalc,
                 use_s2: bool = False, s2_level: int = 15, mon_ids_iv: Optional[List[int]] = None):
        self.remove_from_queue_backlog: Optional[int] = int(
            area.remove_from_queue_backlog) if area.remove_from_queue_backlog else None
        clustering_timedelta: int = int(
            area.priority_queue_clustering_timedelta if area.priority_queue_clustering_timedelta else 0)
        self.delay_after_timestamp_prio: Optional[int] = area.delay_after_prio_event
        strategy: Optional[RaidSpawnPrioStrategy] = None
        if self.delay_after_timestamp_prio is not None:
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
        self._settings: SettingsAreaRaidsMitm = area

        self.starve_route: bool = area.starve_route if area.starve_route is not None else False

    async def _any_coords_left_after_finishing_route(self):
        self._init_route_queue()
        return True

    def _delete_coord_after_fetch(self) -> bool:
        return False

    async def _get_coords_fresh(self, dynamic: bool) -> List[Location]:
        async with self.db_wrapper as session, session:
            coords: List[Location] = await GymHelper.get_locations_in_fence(session, self.geofence_helper)
            if self._settings.including_stops:
                logger.info("Include stops in coords list too!")
                coords.extend(await PokestopHelper.get_locations_in_fence(session, self.geofence_helper))

        return coords

    async def _quit_route(self):
        logger.info("Shutdown Route")
        self._is_started.clear()
        self._round_started_time = None

    def _check_coords_before_returning(self, lat, lng, origin):
        return True
