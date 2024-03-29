from typing import List, Optional

from loguru import logger

from mapadroid.account_handler.AbstractAccountHandler import AccountPurpose
from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.model import SettingsAreaIdle, SettingsRoutecalc
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.route.RouteManagerBase import RouteManagerBase
from mapadroid.route.SubrouteReplacingMixin import SubrouteReplacingMixin
from mapadroid.utils.collections import Location


class RouteManagerIdle(SubrouteReplacingMixin, RouteManagerBase):
    def __init__(self, db_wrapper: DbWrapper, area: SettingsAreaIdle, coords, max_radius, max_coords_within_radius,
                 geofence_helper: GeofenceHelper, routecalc: SettingsRoutecalc,
                 use_s2: bool = False, s2_level: int = 15, mon_ids_iv: Optional[List[int]] = None):
        RouteManagerBase.__init__(self, db_wrapper=db_wrapper, area=area, coords=coords,
                                  max_radius=max_radius,
                                  max_coords_within_radius=max_coords_within_radius,
                                  geofence_helper=geofence_helper,
                                  routecalc=routecalc, use_s2=use_s2, s2_level=s2_level,
                                  mon_ids_iv=mon_ids_iv,
                                  initial_prioq_strategy=None)
        self._settings: SettingsAreaIdle = area
        self.remove_from_queue_backlog = None

    def purpose(self) -> AccountPurpose:
        return AccountPurpose.MON_RAID

    async def _any_coords_left_after_finishing_route(self):
        self._init_route_queue()
        return True

    def _delete_coord_after_fetch(self) -> bool:
        return False

    async def _get_coords_fresh(self, dynamic: bool) -> List[Location]:
        return [Location(0, 0)]

    async def _quit_route(self):
        logger.info("Shutdown Route")
        self._is_started.clear()
        self._round_started_time = None

    def _check_coords_before_returning(self, lat, lng, origin):
        return True

    async def get_next_location(self, origin: str) -> Optional[Location]:
        return Location(0, 0)

    def _may_update_routepool(self):
        return False
