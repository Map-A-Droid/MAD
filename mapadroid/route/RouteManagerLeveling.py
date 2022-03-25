from typing import List, Optional

from loguru import logger

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.helper.PokestopHelper import PokestopHelper
from mapadroid.db.model import SettingsAreaPokestop, SettingsRoutecalc, Pokestop
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.route.RouteManagerBase import RoutePoolEntry
from mapadroid.route.RouteManagerQuests import RouteManagerQuests
from mapadroid.route.routecalc.RoutecalcUtil import RoutecalcUtil
from mapadroid.utils.collections import Location
from mapadroid.utils.madGlobals import QuestLayer, RoutecalculationTypes


class RouteManagerLeveling(RouteManagerQuests):
    def __init__(self, db_wrapper: DbWrapper, area: SettingsAreaPokestop, coords: Optional[List[Location]],
                 max_radius: int, max_coords_within_radius: int,
                 geofence_helper: GeofenceHelper, routecalc: SettingsRoutecalc,
                 mon_ids_iv: Optional[List[int]] = None):
        RouteManagerQuests.__init__(self, db_wrapper=db_wrapper, area=area, coords=coords,
                                    max_radius=max_radius, max_coords_within_radius=max_coords_within_radius,
                                    geofence_helper=geofence_helper, routecalc=routecalc,
                                    mon_ids_iv=mon_ids_iv
                                    )
        self._level = True
        self._stoplist: List[Location] = []

    async def _worker_changed_update_routepools(self):
        with self._manager_mutex:
            logger.info("Updating all routepools in level mode for {} origins", len(self._routepool))
            if len(self._workers_registered) == 0:
                logger.info("No registered workers, aborting __worker_changed_update_routepools...")
                return False

            any_at_all = False
            async with self.db_wrapper as session, session:
                for origin in self._routepool:
                    origin_local_list = []
                    entry: RoutePoolEntry = self._routepool[origin]

                    if len(entry.queue) > 0:
                        logger.debug("origin {} already has a queue, do not touch...", origin)
                        continue
                    unvisited_stops: List[Pokestop] = await PokestopHelper.stops_not_visited(session,
                                                                                             self.geofence_helper,
                                                                                             origin)
                    if len(unvisited_stops) == 0:
                        logger.info("There are no unvisited stops left in DB for {} - nothing more to do!", origin)
                        continue
                    if len(self._route) > 0:
                        logger.info("Making a subroute of unvisited stops..")
                        for coord in self._route:
                            coord_location = Location(coord.lat, coord.lng)
                            if coord_location in self._coords_to_be_ignored:
                                logger.info('Already tried this Stop but it failed spinnable test, skip it')
                                continue
                            for stop in unvisited_stops:
                                if coord_location == Location(float(stop.latitude), float(stop.longitude)):
                                    origin_local_list.append(coord_location)
                    if len(origin_local_list) == 0:
                        logger.info("None of the stops in original route was unvisited, recalc a route")
                        new_route = await self._local_recalc_subroute(unvisited_stops)
                        for coord in new_route:
                            origin_local_list.append(Location(coord.lat, coord.lng))

                    # subroute is all stops unvisited
                    logger.info("Origin {} has {} unvisited stops for this route", origin, len(origin_local_list))
                    entry.subroute = origin_local_list
                    # let's clean the queue just to make sure
                    entry.queue.clear()
                    [entry.queue.append(i) for i in origin_local_list]
                    any_at_all = len(origin_local_list) > 0 or any_at_all
                return any_at_all

    async def _local_recalc_subroute(self, unvisited_stops: List[Pokestop]) -> list[Location]:
        coords: List[Location] = []
        for stop in unvisited_stops:
            coords.append(Location(float(stop.latitude), float(stop.longitude)))
        new_route: list[Location] = await RoutecalcUtil.calculate_route(self.db_wrapper,
                                                                        self._routecalc.routecalc_id,
                                                                        coords,
                                                                        self.get_max_radius(),
                                                                        self.get_max_coords_within_radius(),
                                                                        algorithm=RoutecalculationTypes.OR_TOOLS,
                                                                        use_s2=self.useS2,
                                                                        s2_level=self.S2level,
                                                                        route_name=self.name,
                                                                        overwrite_persisted_route=False,
                                                                        load_persisted_route=False)
        return new_route

    async def _any_coords_left_after_finishing_route(self) -> bool:
        with self._manager_mutex:
            if self._shutdown_route:
                logger.info('Other worker shutdown route - leaving it')
                return False

            if self._start_calc:
                logger.info("Another process already calculate the new route")
                return True
            self._start_calc = True

            any_unvisited = False
            async with self.db_wrapper as session, session:
                for origin in self._routepool:
                    any_unvisited: bool = await PokestopHelper.any_stops_unvisited(session, self.geofence_helper,
                                                                                   origin)
                    if any_unvisited:
                        break

            if not any_unvisited:
                logger.info("Not getting any stops - leaving now.")
                self._shutdown_route = True
                self._start_calc = False
                return False

            # Redo individual routes
            await self._worker_changed_update_routepools()
            self._start_calc = False
            return True

    def _check_unprocessed_stops(self):
        # We finish routes on a per walker/origin level, so the route itself is always the same as long as at
        # least one origin is connected to it.
        return self._stoplist

    async def _get_coords_fresh(self, dynamic: bool) -> List[Location]:
        async with self.db_wrapper as session, session:
            return await PokestopHelper.get_locations_in_fence(session, self.geofence_helper,
                                                               QuestLayer(self._settings.layer))

    def _delete_coord_after_fetch(self) -> bool:
        return False

    async def _quit_route(self):
        await super()._quit_route()
        self._stoplist.clear()

    def _check_coords_before_returning(self, lat: float, lng: float, origin):
        stop = Location(lat, lng)
        logger.info('Checking Stop with ID {}', str(stop))
        if stop in self._coords_to_be_ignored:
            logger.info('Already tried this Stop and failed it')
            return False
        logger.info('DB knows nothing of this stop for {} lets try and go there', origin)
        return True
