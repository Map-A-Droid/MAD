import asyncio
from typing import List, Optional

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.helper.PokestopHelper import PokestopHelper
from mapadroid.db.model import SettingsAreaPokestop, SettingsRoutecalc, Pokestop
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.route.RouteManagerBase import RoutePoolEntry
from mapadroid.route.RouteManagerQuests import RouteManagerQuests
from mapadroid.utils.collections import Location
from loguru import logger


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

    async def _local_recalc_subroute(self, unvisited_stops: List[Pokestop]):
        coords: List[Location] = []
        for stop in unvisited_stops:
            coords.append(Location(float(stop.latitude), float(stop.longitude)))
        new_route = await self._calculate_new_route(coords, self._max_radius, self._max_coords_within_radius,
                                                    False, 1, True)
        return new_route

    async def generate_stop_list(self):
        # TODO: Why is there a sleep here?
        await asyncio.sleep(5)
        async with self.db_wrapper as session, session:
            stops_in_fence: List[Location] = await PokestopHelper.get_locations_in_fence(session, self.geofence_helper)

        logger.info('Detected stops without quests: {}', len(stops_in_fence))
        logger.debug('Detected stops without quests: {}', stops_in_fence)
        self._stoplist: List[Location] = stops_in_fence

    async def _recalc_route_workertype(self):
        await self.recalc_route(self._max_radius, self._max_coords_within_radius, 1, delete_old_route=False,
                                in_memory=True)
        self._init_route_queue()

    async def _get_coords_after_finish_route(self) -> bool:
        with self._manager_mutex:
            if self._shutdown_route:
                logger.info('Other worker shutdown route - leaving it')
                return False

            if self._start_calc:
                logger.info("Another process already calculate the new route")
                return True
            self._start_calc = True
            self._restore_original_route()

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

    def _restore_original_route(self):
        if not self._tempinit:
            logger.info("Restoring original route")
            with self._manager_mutex:
                self._route = self._routecopy.copy()

    def _check_unprocessed_stops(self):
        # We finish routes on a per walker/origin level, so the route itself is always the same as long as at
        # least one origin is connected to it.
        return self._stoplist

    async def start_routemanager(self):
        async with self._manager_mutex:
            if not self._is_started:
                self._is_started = True
                logger.info("Starting routemanager")

                if self._shutdown_route:
                    logger.info('Other worker shutdown route - leaving it')
                    return False

                await self.generate_stop_list()
                stops = self._stoplist
                self._prio_queue = None
                self.delay_after_timestamp_prio = None
                self.starve_route = False
                await self._start_check_routepools()

                if not self._first_started:
                    logger.info("First starting quest route - copying original route for later use")
                    self._routecopy = self._route.copy()
                    self._first_started = True
                else:
                    logger.info("Restoring original route")
                    self._route = self._routecopy.copy()

                new_stops = list(set(stops) - set(self._route))
                if len(new_stops) > 0:
                    logger.info("There's {} new stops not in route", len(new_stops))

                if len(stops) == 0:
                    logger.info('No Stops detected in route - quit worker')
                    self._shutdown_route = True
                    self._restore_original_route()
                    self._route: List[Location] = []
                    return False

                if 0 < len(stops) < len(self._route) \
                        and len(stops) / len(self._route) <= 0.3:
                    # Calculating new route because 70 percent of stops are processed
                    logger.info('There are less stops without quest than route positions - recalc')
                    await self._recalc_stop_route(stops)
                elif len(self._route) == 0 and len(stops) > 0:
                    logger.warning("Something wrong with area: it has a lot of new stops - you should delete the "
                                   "routefile!!")
                    logger.info("Recalc new route for area")
                    await self._recalc_stop_route(stops)
                else:
                    self._init_route_queue()

                logger.info('Getting {} positions', len(self._route))
                return True
        return True

    async def _recalc_stop_route(self, stops):
        self._clear_coords()
        self.add_coords_list(stops)
        self._overwrite_calculation = True
        await self._recalc_route_workertype()
        self._init_route_queue()

    def _delete_coord_after_fetch(self) -> bool:
        return False

    def _quit_route(self):
        super()._quit_route()
        self._stoplist.clear()

    def _check_coords_before_returning(self, lat: float, lng: float, origin):
        if self.init:
            logger.debug('Init Mode - coord is valid')
            return True
        stop = Location(lat, lng)
        logger.info('Checking Stop with ID {}', str(stop))
        if stop in self._coords_to_be_ignored:
            logger.info('Already tried this Stop and failed it')
            return False
        logger.info('DB knows nothing of this stop for {} lets try and go there', origin)
        return True
