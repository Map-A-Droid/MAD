from typing import Dict, List, Optional, Set

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.helper.PokestopHelper import PokestopHelper
from mapadroid.db.model import SettingsAreaPokestop, SettingsRoutecalc
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.route.RouteManagerBase import RouteManagerBase
from mapadroid.route.SubrouteReplacingMixin import SubrouteReplacingMixin
from mapadroid.utils.collections import Location
from mapadroid.utils.geo import get_distance_of_two_points_in_meters
from mapadroid.utils.madGlobals import QuestLayer


class RouteManagerQuests(SubrouteReplacingMixin, RouteManagerBase):
    """
    The locations of single pokestops and the amount of rounds in which they have not been processed
    """
    _stops_not_processed: Dict[Location, int]

    def __init__(self, db_wrapper: DbWrapper, area: SettingsAreaPokestop, coords: Optional[List[Location]],
                 max_radius: int, max_coords_within_radius: int,
                 geofence_helper: GeofenceHelper, routecalc: SettingsRoutecalc,
                 mon_ids_iv: Optional[List[int]] = None):
        RouteManagerBase.__init__(self, db_wrapper=db_wrapper, area=area, coords=coords,
                                  max_radius=max_radius,
                                  max_coords_within_radius=max_coords_within_radius,
                                  geofence_helper=geofence_helper,
                                  routecalc=routecalc, use_s2=False,
                                  mon_ids_iv=mon_ids_iv,
                                  initial_prioq_strategy=None)
        self._settings: SettingsAreaPokestop = area
        """
        List of stops last fetched in _get_coords_fresh containing only those without quests on the layer to be scanned
        """
        self._stoplist: List[Location] = []
        self._stops_not_processed: Dict[Location, int] = {}

    async def _get_coords_fresh(self, dynamic: bool) -> List[Location]:
        logger.info("Fetching coords for quests with dynamic flag {}", dynamic)
        async with self.db_wrapper as session, session:
            if not dynamic:
                return await PokestopHelper.get_locations_in_fence(session, self.geofence_helper)
            else:
                locations_of_stops: List[Location] = await self._get_stops_without_quests_on_layer(session)
                return locations_of_stops

    async def calculate_route(self, dynamic: bool, overwrite_persisted_route: bool = False) -> None:
        if dynamic:
            # also store the latest set in _stoplist
            async with self.db_wrapper as session, session:
                locations_of_stops: List[Location] = await self._get_stops_without_quests_on_layer(session)
            self._stoplist = locations_of_stops
        await super().calculate_route(dynamic, overwrite_persisted_route)

    async def _get_stops_without_quests_on_layer(self, session: AsyncSession) -> List[Location]:
        stops = await PokestopHelper.get_without_quests(session, self.geofence_helper,
                                                        QuestLayer(self._settings.layer))
        locations_of_stops: List[Location] = [Location(float(stop.latitude), float(stop.longitude)) for
                                              stop_id, stop in
                                              stops.items()]
        return locations_of_stops

    async def _any_coords_left_after_finishing_route(self) -> bool:
        async with self._manager_mutex:
            if self._shutdown_route.is_set():
                logger.info('Other worker shutdown - leaving it')
                return False

            if self._start_calc.is_set():
                logger.info("Another process already calculate the new route")
                return True
            if len(self._stoplist) == 0:
                logger.info("No new stops - leaving now.")
                await self.stop_routemanager()
                return False
            async with self.db_wrapper as session, session:
                locations_of_stops: List[Location] = await self._get_stops_without_quests_on_layer(session)
            # remove coords to be ignored from coords
            locations_of_stops = [coord for coord in locations_of_stops if coord not in self._coords_to_be_ignored]
            if len(locations_of_stops) > 0:
                logger.info("Getting new coords - recalculating route")
                await self.calculate_route(True)
            else:
                logger.info("Dont getting new stops - leaving now.")
                await self.stop_routemanager()
                return False
            return True

    async def start_routemanager(self):
        if self._shutdown_route.is_set():
            logger.info('Route is shutting down already.')
            return False
        if self._is_started.is_set():
            logger.info('Route has been started or is in the process of starting.')
            return True

        async with self._manager_mutex:
            logger.info("Starting routemanager")
            self._is_started.set()

            await self.calculate_route(dynamic=True, overwrite_persisted_route=False)
            await self._start_check_routepools()

            logger.info('Getting {} positions in route', len(self._route))
            return True

    def _delete_coord_after_fetch(self) -> bool:
        return True

    async def _quit_route(self):
        logger.info('Shutdown Route')
        if self._is_started.is_set():
            async with self._manager_mutex:
                self._shutdown_route.set()
                self._is_started.clear()
                self._round_started_time = None

        # clear not processed stops
        # TODO: Does this even make sense? Maybe all devices just disconnected and are going to come back
        #  However, the next round (next day) could have some leftovers here...
        self._stops_not_processed.clear()
        self._coords_to_be_ignored.clear()

    def _check_coords_before_returning(self, lat: float, lng: float, origin):
        stop = Location(lat, lng)
        logger.info('Checking Stop at {:.5f}, {:.5f}', lat, lng)
        if stop in self._coords_to_be_ignored or not self._is_coord_within_range_of_stoplist(stop):
            logger.info('Already got this stop or stop is out of range of stops to be scanned')
            return False
        logger.debug('Got new Stop')
        return True

    def _should_get_new_coords_after_finishing_route(self) -> bool:
        return True

    def get_quest_layer_to_scan(self) -> Optional[int]:
        return self._settings.layer

    def _is_coord_within_range_of_stoplist(self, location: Location) -> bool:
        if self._max_clustering == 1:
            return location in self._stoplist
        elif location in self._stoplist:
            # Clustering is enabled but the stoplist contains the location to be checked. I.e., the location
            # only has one stop in range that is to be scanned
            return True
        # Clustering is enabled, go through the stoplist one by one and check the range
        for stop in self._stoplist:
            if get_distance_of_two_points_in_meters(stop.lat, stop.lng,
                                                    location.lat, location.lng) < self.get_max_radius():
                return True
        return False
