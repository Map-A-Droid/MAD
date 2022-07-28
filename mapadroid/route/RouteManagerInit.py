from typing import List, Optional

from loguru import logger

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.model import SettingsAreaInitMitm, SettingsRoutecalc
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.route.RouteManagerBase import RouteManagerBase
from mapadroid.route.SubrouteReplacingMixin import SubrouteReplacingMixin
from mapadroid.utils.collections import Location
from mapadroid.utils.s2Helper import S2Helper


class RouteManagerInit(SubrouteReplacingMixin, RouteManagerBase):
    def __init__(self, db_wrapper: DbWrapper, area: SettingsAreaInitMitm, coords, max_radius, max_coords_within_radius,
                 geofence_helper: GeofenceHelper, routecalc: SettingsRoutecalc,
                 use_s2: bool = False, s2_level: int = 15, mon_ids_iv: Optional[List[int]] = None):
        # TODO: Mon Despawn targetted "learning"?
        RouteManagerBase.__init__(self, db_wrapper=db_wrapper, area=area, coords=coords,
                                  max_radius=max_radius,
                                  max_coords_within_radius=max_coords_within_radius,
                                  geofence_helper=geofence_helper,
                                  routecalc=routecalc, use_s2=use_s2, s2_level=s2_level,
                                  mon_ids_iv=mon_ids_iv,
                                  initial_prioq_strategy=None)
        self._settings: SettingsAreaInitMitm = area
        self.remove_from_queue_backlog = None

    def _delete_coord_after_fetch(self) -> bool:
        return False

    async def _get_coords_fresh(self, dynamic: bool) -> List[Location]:
        # Take the max radius times 2 as the areas would overlap otherwise
        return S2Helper.generate_locations(self.get_max_radius() * 2, self.get_geofence_helper())

    async def _quit_route(self):
        logger.info("Shutdown Route")
        self._is_started.clear()
        self._round_started_time = None

    def _check_coords_before_returning(self, lat, lng, origin):
        return True

    async def _any_coords_left_after_finishing_route(self) -> bool:
        return True

    def _should_get_new_coords_after_finishing_route(self) -> bool:
        # Subtract one round as this is called when the
        # TODO
        return self._settings.init_mode_rounds > 1

    async def calculate_route(self, dynamic: bool, overwrite_persisted_route: bool = False) -> None:
        coords: List[Location] = await self._get_coords_fresh(dynamic)
        if dynamic:
            coords = [coord for coord in coords if coord not in self._coords_to_be_ignored]
        async with self._manager_mutex:
            self._route = coords
            self._current_route_round_coords = self._route.copy()
            self._init_route_queue()
            await self._update_routepool()
