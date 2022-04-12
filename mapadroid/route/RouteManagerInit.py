from typing import List, Optional

from loguru import logger

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.model import SettingsRoutecalc, SettingsAreaInitMitm
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.route.RouteManagerBase import RouteManagerBase
from mapadroid.utils.collections import Location
from mapadroid.utils.s2Helper import S2Helper


class RouteManagerInit(RouteManagerBase):
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

    def _delete_coord_after_fetch(self) -> bool:
        return False

    async def _get_coords_fresh(self, dynamic: bool) -> List[Location]:
        return S2Helper.generate_locations(self.get_max_radius(), self.get_geofence_helper())

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
