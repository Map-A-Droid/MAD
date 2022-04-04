from typing import List, Optional

from loguru import logger

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.helper.PokestopHelper import PokestopHelper
from mapadroid.db.model import SettingsAreaPokestop, SettingsRoutecalc
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.route.RouteManagerBase import RouteManagerBase
from mapadroid.utils.collections import Location
from mapadroid.utils.geo import get_distance_of_two_points_in_meters
from mapadroid.utils.madGlobals import QuestLayer


class RouteManagerQuests(RouteManagerBase):
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
        self._calctype: str = area.route_calc_algorithm
        self._stoplist: List[Location] = []
        self._routecopy: List[Location] = []
        self._tempinit: bool = False

    async def _get_coords_fresh(self, dynamic: bool) -> List[Location]:
        async with self.db_wrapper as session, session:
            if not dynamic:
                return await PokestopHelper.get_locations_in_fence(session, self.geofence_helper,
                                                                   QuestLayer(self._settings.layer))
            else:
                stops = await PokestopHelper.get_without_quests(session, self.geofence_helper,
                                                                QuestLayer(self._settings.layer))
                locations_of_stops: List[Location] = [Location(float(stop.latitude), float(stop.longitude)) for
                                                      stop_id, stop in
                                                      stops.items()]
                # also store the latest set in _stoplist
                self._stoplist = locations_of_stops
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
            coords: List[Location] = self._check_unprocessed_stops()
            # remove coords to be ignored from coords
            coords = [coord for coord in coords if coord not in self._coords_to_be_ignored]
            # TODO: Move all the calculation stuff out of a simple checking routine
            if len(coords) > 0:
                logger.info("Getting new coords - recalculating route")
                await self.calculate_route(True)
            else:
                logger.info("Dont getting new stops - leaving now.")
                await self.stop_routemanager()
                return False
            return True

    def _check_unprocessed_stops(self):
        list_of_stops_to_return: List[Location] = []

        if len(self._stoplist) == 0:
            return list_of_stops_to_return
        else:
            # we only want to add stops that we haven't spun yet
            # This routine's result is evaluated below
            for stop in self._stoplist:
                if stop not in self._stops_not_processed and stop not in self._get_unprocessed_coords_from_worker():
                    self._stops_not_processed[stop] = 1
                else:
                    self._stops_not_processed[stop] += 1

        for stop, error_count in self._stops_not_processed.items():
            if stop not in self._stoplist:
                logger.info("Location {} is no longer in our stoplist and will be ignored", stop)
                self._coords_to_be_ignored.add(stop)
            elif error_count < 4:
                logger.info("Found stop not processed yet: {}", stop)
                list_of_stops_to_return.append(stop)
            else:
                logger.warning("Stop {} has not been processed thrice in a row, please check your DB", stop)
                self._coords_to_be_ignored.add(stop)

        if len(list_of_stops_to_return) > 0:
            logger.info("Found stops not yet processed, retrying those in the next round")
        return list_of_stops_to_return

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
            self._init_route_queue()

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
        logger.info('Checking Stop with ID {}', stop)
        if stop in self._coords_to_be_ignored or not self._is_coord_within_range_of_stoplist(stop):
            logger.info('Already got this stop or stop is out of range of stops to be scanned')
            return False
        logger.info('Getting new Stop')
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
