import asyncio
import collections
import math
import time
from abc import ABC, abstractmethod
from asyncio import Task, CancelledError
from dataclasses import dataclass
from operator import itemgetter
from typing import Dict, List, Optional, Set, Tuple

from asyncio_rlock import RLock
from loguru import logger

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.model import SettingsArea, SettingsRoutecalc
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.route.prioq.RoutePriorityQueue import RoutePriorityQueue
from mapadroid.route.prioq.strategy.AbstractRoutePriorityQueueStrategy import AbstractRoutePriorityQueueStrategy, \
    RoutePriorityQueueEntry
from mapadroid.route.routecalc.RoutecalcUtil import RoutecalcUtil
from mapadroid.utils.DatetimeWrapper import DatetimeWrapper
from mapadroid.utils.collections import Location
from mapadroid.utils.geo import get_distance_of_two_points_in_meters
from mapadroid.utils.madGlobals import PositionType, PrioQueueNoDueEntry, RoutecalculationTypes, \
    RoutemanagerShuttingDown
from mapadroid.utils.walkerArgs import parse_args
from mapadroid.worker.WorkerType import WorkerType

args = parse_args()
# Duration in seconds to be waited for a route to be recalculated
RECALC_WAIT_DURATION: int = 600

Relation = collections.namedtuple(
    'Relation', ['other_event', 'distance', 'timedelta'])


@dataclass
class RoutePoolEntry:
    last_access: float
    queue: collections.deque
    subroute: List[Location]
    time_added: float
    rounds: int = 0
    current_pos: Location = Location(0.0, 0.0)
    prio_coord: Optional[Location] = None
    worker_sleeping: float = 0
    last_position_type: PositionType = PositionType.NORMAL


class RouteManagerBase(ABC):
    def __init__(self, db_wrapper: DbWrapper, area: SettingsArea, coords: Optional[List[Location]],
                 max_radius: float,
                 max_coords_within_radius: int,
                 geofence_helper: GeofenceHelper,
                 routecalc: SettingsRoutecalc,
                 initial_prioq_strategy: Optional[AbstractRoutePriorityQueueStrategy],
                 use_s2: bool = False, s2_level: int = 15,
                 joinqueue=None, mon_ids_iv: Optional[List[int]] = None):
        if mon_ids_iv is None:
            mon_ids_iv = []

        self.db_wrapper: DbWrapper = db_wrapper
        self.name: str = area.name
        self.useS2: bool = use_s2
        self.S2level: int = s2_level
        self.area_id = area.area_id

        self._coords_unstructured: List[Location] = coords
        self.geofence_helper: GeofenceHelper = geofence_helper
        self._routecalc: SettingsRoutecalc = routecalc
        self._max_radius: float = max_radius
        self._max_coords_within_radius: int = max_coords_within_radius
        # TODO For better typing, we can assign the type with the following if/else. Ugly but better to work with?
        #  Or move usages of self.settings to the classes inheriting...
        self._settings: SettingsArea = area
        self._mode: WorkerType = WorkerType(area.mode)
        self._is_started: asyncio.Event = asyncio.Event()
        self._first_started = False
        self._current_route_round_coords: List[Location] = []
        self._start_calc: asyncio.Event = asyncio.Event()
        self._coords_to_be_ignored = set()
        # self._level = area.level if area.mode == "pokestop" else False
        # self._calctype = area.route_calc_algorithm if area.mode == "pokestop" else "route"
        self._calctype = "route"
        self._overwrite_calculation: bool = False
        self._stops_not_processed: Dict[Location, int] = {}
        self._routepool: Dict[str, RoutePoolEntry] = {}
        self._roundcount: int = 0
        self._joinqueue = joinqueue
        self._worker_start_position: Dict[str] = {}
        self._manager_mutex: RLock = RLock()
        # we want to store the workers using the routemanager
        self._workers_registered: Set[str] = set()
        self._round_started_time = None
        self._route: List[Location] = []

        # TOOD: Only allow this in some classmethod...
        # if coords is not None:
        #     if self.init:
        #         fenced_coords = coords
        #     else:
        #         fenced_coords = self.geofence_helper.get_geofenced_coordinates(
        #             coords)
        #     # TODO.... adjust
        #     new_coords = self._route_resource.get_json_route(fenced_coords, int(max_radius),
        #                                                      max_coords_within_radius,
        #                                                      algorithm=self._calctype, route_name=self.name,
        #                                                      in_memory=False)
        #     for coord in new_coords:
        #         self._route.append(Location(coord["lat"], coord["lng"]))
        self._max_clustering: int = self._max_coords_within_radius
        self.delay_after_timestamp_prio: int = 0
        self.starve_route: bool = False
        self.remove_from_queue_backlog: Optional[int] = 0
        self._mon_ids_iv: List[int] = mon_ids_iv
        # initialize priority queue variables
        if initial_prioq_strategy:
            self._prio_queue: Optional[RoutePriorityQueue] = RoutePriorityQueue(initial_prioq_strategy)
        else:
            self._prio_queue: Optional[RoutePriorityQueue] = None
        self._check_routepools_thread: Optional[Task] = None
        self._shutdown_route: asyncio.Event = asyncio.Event()

    def get_ids_iv(self) -> List[int]:
        return self._mon_ids_iv

    def get_max_radius(self):
        return self._max_radius

    def get_max_coords_within_radius(self):
        return self._max_coords_within_radius

    async def set_priority_queue_strategy(self, new_strategy: Optional[AbstractRoutePriorityQueueStrategy]) -> None:
        if not new_strategy:
            await self._prio_queue.stop()
            self._prio_queue = None
        else:
            if not self._prio_queue:
                self._prio_queue = RoutePriorityQueue(new_strategy)
                await self._prio_queue.start()
            else:
                self._prio_queue.strategy = new_strategy

    async def _start_check_routepools(self):
        loop = asyncio.get_running_loop()
        self._check_routepools_thread: Task = loop.create_task(self._check_routepools())

    async def _stop_internal_tasks(self):
        logger.info("Shutdown Route Threads")
        if self._prio_queue:
            await self._prio_queue.stop()
        logger.debug("Shutdown Prio Queue Thread - done...")
        if self._check_routepools_thread is not None:
            self._check_routepools_thread.cancel()
        self._check_routepools_thread: Optional[Task] = None
        self._shutdown_route.clear()
        logger.info("Shutdown Route Threads completed")

    async def stop_routemanager(self):
        # call routetype stoppper
        if not self._shutdown_route.is_set():
            async with self._manager_mutex:
                self._shutdown_route.set()
                self._is_started.clear()
                await self._quit_route()
                await self._stop_internal_tasks()

        logger.info("Shutdown of route completed")

    def _init_route_queue(self):
        if len(self._route) > 0:
            self._current_route_round_coords.clear()
            logger.debug("Creating queue for coords")
            for latlng in self._route:
                self._current_route_round_coords.append(latlng)
            logger.debug("Finished creating queue")

    def _clear_coords(self):
        self._coords_unstructured = None

    async def register_worker(self, worker_name) -> bool:
        async with self._manager_mutex:
            if worker_name in self._workers_registered:
                logger.info("already registered")
                return False
            else:
                logger.info("registering to routemanager")
                self._workers_registered.add(worker_name)
                return True

    async def unregister_worker(self, worker_name, remove_routepool_entry: bool = False):
        async with self._manager_mutex:
            if worker_name in self._workers_registered:
                logger.info("unregistering from routemanager")
                self._workers_registered.remove(worker_name)
            else:
                logger.info("failed unregistering from routemanager since subscription was previously lifted")
            if remove_routepool_entry and worker_name in self._routepool:
                logger.info("Deleting old routepool of {}", worker_name)
                del self._routepool[worker_name]
            if len(self._workers_registered) == 0 and self._is_started.is_set():
                logger.info("Routemanager does not have any subscribing workers anymore, calling stop", self.name)
                await self.stop_routemanager()

    async def _start_priority_queue(self):
        if self._prio_queue:
            await self._prio_queue.start()

    async def calculate_route(self, dynamic: bool, overwrite_persisted_route: bool = False) -> None:
        """
        Calculates a new route based off the internal acquisition of coords within the routemanager itself.

        :param dynamic: If True, coords to be ignored are respected and route is not loaded from the DB
        :param overwrite_persisted_route: Whether the calculated route should be persisted in the database (True -> persist)
        """
        # If dynamic, recalc using OR tools in all cases (if possible) and do not persist to DB
        coords: list[Location] = await self._get_coords_fresh(dynamic)
        if dynamic:
            coords = [coord for coord in coords if coord not in self._coords_to_be_ignored]
        if not coords:
            # Empty route, return immediately after shutdown
            await self.stop_routemanager()
            raise RoutemanagerShuttingDown("No coords to calculate a route")
        try:
            self._start_calc.set()
            new_route: list[Location] = await RoutecalcUtil.calculate_route(self.db_wrapper,
                                                                            self._routecalc.routecalc_id,
                                                                            coords,
                                                                            self.get_max_radius(),
                                                                            self.get_max_coords_within_radius(),
                                                                            algorithm=RoutecalculationTypes.OR_TOOLS,
                                                                            use_s2=self.useS2,
                                                                            s2_level=self.S2level,
                                                                            route_name=self.name,
                                                                            overwrite_persisted_route=overwrite_persisted_route,
                                                                            load_persisted_route=not dynamic)
        except Exception as e:
            logger.exception(e)
            raise e
        finally:
            self._start_calc.clear()
        async with self._manager_mutex:
            self._route = new_route
            self._current_route_round_coords = self._route.copy()
            # TODO: Also reset the subroutes of the workers?
            self._init_route_queue()
            await self._worker_changed_update_routepools()

    def date_diff_in_seconds(self, dt2, dt1):
        timedelta = dt2 - dt1
        return timedelta.days * 24 * 3600 + timedelta.seconds

    def dhms_from_seconds(self, seconds):
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return hours, minutes, seconds

    def _get_round_finished_string(self):
        round_finish_time = DatetimeWrapper.now()
        round_completed_in = ("%d hours, %d minutes, %d seconds" % (self.dhms_from_seconds(self.date_diff_in_seconds(
            round_finish_time,
            self._round_started_time))))
        return round_completed_in

    def add_coord_to_be_removed(self, lat: float, lon: float):
        if lat < -90.0 or lat > 90.0 or lon < -180.0 or lon > 180.0:
            return
        self._coords_to_be_ignored.add(Location(lat, lon))

    @abstractmethod
    async def start_routemanager(self):
        """
        Starts priority queue or whatever the implementations require
        :return:
        """
        pass

    @abstractmethod
    async def _quit_route(self):
        """
        Killing the Route Thread
        :return:
        """
        pass

    @abstractmethod
    async def _get_coords_fresh(self, dynamic: bool) -> List[Location]:
        """
        Return list of coords to be fetched and used for routecalc
        :param dynamic: Whether the coord should be retrieved as if the scanning is taking place for the first time or
        some data has been processed already (e.g., some stops having been scanned for quests already)
        :return:
        """
        pass

    @abstractmethod
    def _check_coords_before_returning(self, lat, lng, origin) -> bool:
        """
        Returns whether the location passed should be visited or not
        :return:
        """
        pass

    @abstractmethod
    async def _any_coords_left_after_finishing_route(self) -> bool:
        """
        :return:
        """
        pass

    @abstractmethod
    def _delete_coord_after_fetch(self) -> bool:
        """
        Whether coords fetched from get_next_location should be removed from the total route
        :return:
        """

    def _should_get_new_coords_after_finishing_route(self) -> bool:
        """
        Whether the route should be updated with coords after finishing a route
        Returns: False by default. Subclasses of RouteManagerBase may overwrite if needed
        """
        return False

    def _has_normal_route(self) -> bool:
        """
        Whether or not we have a normal route from which to pull the next
        location. This exists so subclasses can perform their own logic,
        if necessary. E.g., 'iv_mitm' returns False.
        """
        return True

    def _can_pass_prioq_coords(self) -> bool:
        """
        Whether or not passing prioq coords to another closer worker is
        allowed. This exists so subclasses can perform their own logic,
        if necessary. E.g., 'iv_mitm' returns False.
        """
        return True

    def __set_routepool_entry_location(self, origin: str, pos: Location):
        if self._routepool.get(origin, None) is not None:
            self._routepool[origin].current_pos = pos
            self._routepool[origin].last_access = time.time()
            self._routepool[origin].worker_sleeping = 0

    async def _wait_for_calc_end(self, origin: str) -> None:
        while self._start_calc.is_set():
            # in order to prevent the worker from being removed from the routepool (if registered at all)
            if origin in self._routepool:
                self._routepool[origin].last_access = time.time()
            await asyncio.sleep(1)

    async def get_next_location(self, origin: str) -> Optional[Location]:
        logger.debug4("get_next_location called")
        if self._shutdown_route.is_set():
            raise RoutemanagerShuttingDown("Routemanager is shutting down, not requesting a new location")
        if not self._is_started.is_set():
            logger.info("Starting routemanager in get_next_location")
            if not await self.start_routemanager():
                logger.info('No coords available - quit worker')
                return None

        if self._start_calc.is_set():
            logger.info("Another process is already calculating a new route")
            try:
                await asyncio.wait_for(self._wait_for_calc_end(origin), RECALC_WAIT_DURATION)
            except (CancelledError, asyncio.exceptions.TimeoutError):
                logger.info("Current recalc took too long, returning None location")
                return None
        if origin not in self._workers_registered:
            await self.register_worker(origin)

        routepool_entry: RoutePoolEntry = self._routepool.get(origin, None)
        if not routepool_entry:
            logger.debug("No subroute/routepool entry present, creating it")
            routepool_entry = RoutePoolEntry(time.time(), collections.deque(), [], time_added=time.time())
            self._routepool[origin] = routepool_entry
            if origin in self._worker_start_position:
                routepool_entry.current_pos = self._worker_start_position[origin]
            if not await self._worker_changed_update_routepools():
                logger.info("Failed updating routepools after adding a worker to it")
                return None
        elif routepool_entry.prio_coord and self._can_pass_prioq_coords():
            prioevent = routepool_entry.prio_coord
            routepool_entry.prio_coord = None
            logger.info('getting a nearby prio event {}', prioevent)
            self.__set_routepool_entry_location(origin, prioevent)
            routepool_entry.last_position_type = PositionType.PRIOQ
            return prioevent

        # first check if a location is available, if not, block until we have one...

        # check priority queue for items of priority that are past our time...
        # if that is not the case, simply increase the index in route and return the location on route
        logger.debug("Trying to fetch a location from routepool")
        # determine whether we move to the next location or the prio queue top's item
        if self._prio_queue and (not routepool_entry.last_position_type == PositionType.PRIOQ
                                 or self.starve_route):
            logger.debug2("Checking for prioQ entries")
            # Check the PrioQ
            try:
                next_timestamp, next_coord = None, None
                if not self._has_normal_route():
                    # "blocking" to wait for a coord
                    while not next_timestamp:
                        try:
                            prioq_entry: RoutePriorityQueueEntry = await self._prio_queue.pop_event()
                            next_timestamp = prioq_entry.timestamp_due
                            next_coord = prioq_entry.location
                        except (PrioQueueNoDueEntry, asyncio.TimeoutError):
                            # No item available yet, sleep
                            await asyncio.sleep(1)
                else:
                    logger.debug2("Popping prioQ")
                    prioq_entry: RoutePriorityQueueEntry = await self._prio_queue.pop_event()
                    next_timestamp = prioq_entry.timestamp_due
                    next_coord = prioq_entry.location

                next_readable_time = DatetimeWrapper.fromtimestamp(next_timestamp).strftime('%Y-%m-%d %H:%M:%S')
                now = time.time()
                if next_timestamp > now:
                    raise PrioQueueNoDueEntry("Next event at {} has not taken place yet", next_readable_time)
                if self._remove_deprecated_prio_events():
                    if self.remove_from_queue_backlog not in [None, 0]:
                        delete_before = now - self.remove_from_queue_backlog
                    else:
                        delete_before = 0

                    while next_timestamp < delete_before:
                        # TODO: Move task_done elsewhere?
                        logger.debug("Popping prio Q")
                        prioq_entry: RoutePriorityQueueEntry = await self._prio_queue.pop_event()
                        next_timestamp = prioq_entry.timestamp_due
                        next_coord = prioq_entry.location
                        next_readable_time = DatetimeWrapper.fromtimestamp(next_timestamp).strftime('%Y-%m-%d %H:%M:%S')
                        if next_timestamp < delete_before:
                            logger.warning(
                                "Prio event surpassed the maximum backlog time and will be skipped. Make "
                                "sure you run enough workers or reduce the size of the area! (event was "
                                "scheduled for {})", next_readable_time)
                if self._can_pass_prioq_coords():
                    while (not self._check_coord_and_remove_from_route_if_applicable(next_coord, origin)
                           or self._other_worker_closer_to_prioq(next_coord, origin)):
                        logger.info("Invalid prio event or scheduled for {} passed to a closer worker.",
                                    next_readable_time)
                        prioq_entry: RoutePriorityQueueEntry = await self._prio_queue.pop_event()
                        # TODO: Handle timestamp or ignore it given above while loop should have dealt with deprecated
                        #  stops if applicable
                        next_timestamp = prioq_entry.timestamp_due
                        next_coord = prioq_entry.location

                routepool_entry.last_position_type = PositionType.PRIOQ
                logger.debug("Moving to {}, {} for a priority event scheduled for {}", next_coord.lat,
                             next_coord.lng, next_readable_time)
                self.__set_routepool_entry_location(origin, next_coord)
                return next_coord
            except (IndexError, PrioQueueNoDueEntry, asyncio.TimeoutError):
                # Get next coord "normally"
                logger.debug("No prioQ location available")
                pass

        logger.debug("Moving on with route")
        routepool_entry.last_position_type = PositionType.NORMAL
        # TODO: this check is likely always true now.............
        if self._get_worker_rounds_run_through() > self._roundcount:
            self._roundcount = self._get_worker_rounds_run_through()
            if self._round_started_time is not None:
                logger.info("All subroutes reached the first spot again. It took {}",
                            self._get_round_finished_string())
            self._round_started_time = DatetimeWrapper.now()
            if len(self._route) == 0:
                return None
            logger.info("Round started at {}", self._round_started_time)
        elif self._round_started_time is None:
            self._round_started_time = DatetimeWrapper.now()

        if len(routepool_entry.queue) == 0:
            # worker done with his subroute
            routepool_entry.rounds += 1
        if len(self._current_route_round_coords) >= 0 and len(routepool_entry.queue) == 0:
            # only quest could hit this else!
            logger.info("finished subroute, updating all subroutes if necessary")

            if self._should_get_new_coords_after_finishing_route():
                # check for coords not in other workers to get a real open coord list
                if not await self._any_coords_left_after_finishing_route():
                    logger.info("No more coords available - don't update routepool")
                    return None
                else:
                    await self.calculate_route(True)

            if not await self._worker_changed_update_routepools():
                logger.info("Failed updating routepools ...")
                return None

            if len(routepool_entry.queue) == 0 and len(routepool_entry.subroute) == 0:
                logger.info("Subroute-update won't help or queue and subroute are empty, signaling worker to "
                            "reconnect")
                routepool_entry.last_access = time.time()
                return None
            elif len(routepool_entry.queue) == 0 and len(routepool_entry.subroute) > 0:
                [routepool_entry.queue.append(i) for i in routepool_entry.subroute]
            elif len(routepool_entry.queue) > 0 and len(routepool_entry.subroute) > 0:
                logger.info("Getting new coords")
            else:
                logger.info("Not getting new coords - leaving worker")
                return None

        if len(routepool_entry.queue) == 0:
            logger.warning("Having updated routepools and checked lengths of queue and subroute, "
                           "queue is still empty, signaling worker to stop whatever he is doing")
            routepool_entry.last_access = time.time()
            return None

        # Recurse removal for very very large queue sizes - we know we should find the next available coord now
        # Indexerror should not be an issue as the queue must have been filled by now
        next_coord = routepool_entry.queue.popleft()
        logger.info("Moving on with location {}, {} [{} coords left (Workerpool)]", next_coord.lat,
                    next_coord.lng, len(routepool_entry.queue) + 1)
        while (len(routepool_entry.queue) > 0
               and not self._check_coord_and_remove_from_route_if_applicable(next_coord, origin)):
            next_coord = routepool_entry.queue.popleft()
            logger.info("Moving on with location {}, {} [{} coords left (Workerpool)]", next_coord.lat,
                        next_coord.lng, len(routepool_entry.queue) + 1)
        if not self._check_coord_and_remove_from_route_if_applicable(next_coord, origin):
            logger.info("Location in routepool ({}) is not to be scanned", next_coord)
            return None
        self.__set_routepool_entry_location(origin, next_coord)
        return next_coord

    def _check_coord_and_remove_from_route_if_applicable(self, next_coord, origin) -> bool:
        """
        In case the coord is to only be visited once, the RouteManager child class can decide if the coord is to be
        removed from the route.
        Args:
            next_coord:
            origin:

        Returns: False if the coord is not to be visited, True otherwise

        """
        if self._check_coords_before_returning(next_coord.lat, next_coord.lng, origin):
            if self._delete_coord_after_fetch() and next_coord in self._current_route_round_coords:
                self._current_route_round_coords.remove(next_coord)
            return True
        return False

    def _get_worker_rounds_run_through(self) -> int:
        temp_worker_round_list: list = []
        for _origin, entry in self._routepool.items():
            temp_worker_round_list.append(entry.rounds)

        return 0 if len(temp_worker_round_list) == 0 else min(temp_worker_round_list)

    def _get_unprocessed_coords_from_worker(self) -> list:
        unprocessed_coords: list = []
        for _origin, entry in self._routepool.items():
            unprocessed_coords.append(entry.queue)

        return unprocessed_coords

    def _other_worker_closer_to_prioq(self, prioqcoord, origin):
        logger.debug('Check distances from worker to PrioQ coord')
        closer_worker = None
        if len(self._workers_registered) == 1:
            logger.debug('Route has only one worker - no distance check')
            return False
        elif origin not in self._routepool:
            return False

        current_worker_pos = self._routepool[origin].current_pos
        distance_worker = get_distance_of_two_points_in_meters(current_worker_pos.lat, current_worker_pos.lng,
                                                               prioqcoord.lat, prioqcoord.lng)

        logger.debug("distance to PrioQ {}: {}", prioqcoord, distance_worker)
        temp_distance = distance_worker

        for worker in self._routepool.keys():
            if worker == origin or self._routepool[worker].prio_coord \
                    or self._routepool[origin].last_position_type == PositionType.PRIOQ:
                continue
            worker_pos = self._routepool[worker].current_pos
            prio_distance = get_distance_of_two_points_in_meters(worker_pos.lat, worker_pos.lng,
                                                                 prioqcoord.lat, prioqcoord.lng)
            logger.debug("distance to PrioQ {}: {}", prioqcoord, prio_distance)
            if prio_distance < temp_distance:
                logger.debug("Worker {} closer by {} meters", worker,
                             int(distance_worker) - int(prio_distance))
                temp_distance = prio_distance
                closer_worker = worker

        if closer_worker is not None:
            self._routepool[closer_worker].prio_coord = prioqcoord
            logger.debug("Worker {} is closer to PrioQ event {}", closer_worker, prioqcoord)
            return True

        logger.debug("No Worker is closer to PrioQ event {}", prioqcoord)

        return False

    # to be called regularly to remove inactive workers that used to be registered
    async def _check_routepools(self, timeout: int = 300):
        while not self._shutdown_route.is_set():
            logger.debug("Checking routepool for idle/dead workers")
            for origin in list(self._routepool):
                entry: RoutePoolEntry = self._routepool[origin]
                if time.time() - entry.last_access > timeout + entry.worker_sleeping:
                    logger.warning("Worker {} has not accessed a location in {} seconds, removing from "
                                   "routemanager", origin, timeout)
                    await self.unregister_worker(origin, True)
            await asyncio.sleep(60)

    def set_worker_sleeping(self, origin: str, sleep_duration: float) -> None:
        if sleep_duration > 0 and origin in self._routepool:
            self._routepool[origin].worker_sleeping = sleep_duration

    async def _worker_changed_update_routepools(self):
        less_coords: bool = False
        workers: int = 0
        if not self._is_started.is_set():
            return True
        # TODO: Idle mode...
        if not self._may_update_routepool() and len(self._current_route_round_coords) == 0:
            logger.info("No more coords - breakup")
            return False
        elif not self._may_update_routepool():
            logger.info('Not updating routepools in iv_mitm mode')
            return True

        logger.debug("Updating all routepools")
        workers = len(self._routepool)
        if len(self._workers_registered) == 0 or workers == 0:
            logger.info("No registered workers, aborting __worker_changed_update_routepools...")
            return False

        logger.debug("Current route for all workers: {}", self._current_route_round_coords)
        logger.info("Current route for all workers length: {}", len(self._current_route_round_coords))

        if workers > len(self._current_route_round_coords):
            less_coords = True
            new_subroute_length = len(self._current_route_round_coords)
            extra_length_workers = 0
        else:
            try:
                new_subroute_length = math.floor(len(self._current_route_round_coords) /
                                                 workers)
                if new_subroute_length == 0:
                    return False
                extra_length_workers = len(self._current_route_round_coords) % workers
            except Exception:
                logger.info('Something happens with the worker - breakup')
                return False
        i: int = 0
        temp_total_round: collections.deque = collections.deque(self._current_route_round_coords)

        logger.debug("Workers in route: {}", workers)
        if extra_length_workers > 0:
            logger.debug("New subroute length: {}-{}", new_subroute_length, new_subroute_length + 1)
        else:
            logger.debug("New subroute length: {}", new_subroute_length)

        # we want to order the dict by the time's we added the workers to the areas
        # we first need to build a list of tuples with only origin, time_added
        logger.debug("Checking routepool: {}", self._routepool)
        reduced_routepools = [(origin, self._routepool[origin].time_added) for origin in
                              self._routepool]
        sorted_routepools = sorted(reduced_routepools, key=itemgetter(1))

        logger.debug("Checking routepools in the following order: {}", sorted_routepools)
        compare = lambda x, y: collections.Counter(x) == collections.Counter(y)  # noqa: E731
        for origin, _time_added in sorted_routepools:
            if origin not in self._routepool:
                # TODO probably should restart this job or something
                logger.info('{} must have unregistered when we weren\'t looking.. skip it', origin)
                continue
            entry: RoutePoolEntry = self._routepool[origin]
            logger.debug("Checking subroute of {}", origin)
            # let's assume a worker has already been removed or added to the dict (keys)...

            new_subroute: List[Location] = []
            subroute_index: int = 0
            new_subroute_actual_length = new_subroute_length
            if i < extra_length_workers:
                new_subroute_actual_length += 1
            while len(temp_total_round) > 0 and subroute_index < new_subroute_actual_length:
                subroute_index += 1
                new_subroute.append(temp_total_round.popleft())

            logger.debug3("New Subroute for worker {}: {}", origin, new_subroute)
            logger.debug3("Old Subroute for worker {}: {}", origin, entry.subroute)

            i += 1
            if len(entry.subroute) == 0:
                logger.debug("{}'s subroute is empty, assuming he has freshly registered and desperately "
                             "needs a queue", origin)
                # worker is freshly registering, pass him his fair share
                entry.subroute = new_subroute
                # let's clean the queue just to make sure
                entry.queue.clear()
            elif len(new_subroute) == len(entry.subroute):
                logger.debug("{}'s subroute is as long as the old one, we will assume it hasn't changed "
                             "(for now)", origin)
                # apparently nothing changed
                if compare(new_subroute, entry.subroute):
                    logger.info("Apparently no changes in subroutes...")
                else:
                    logger.info("Subroute of {} has changed. Replacing entirely", origin)
                    # TODO: what now?
                    logger.debug4('new_subroute: {}', new_subroute)
                    logger.debug4('entry.subroute: {}', entry.subroute)
                    logger.debug('new_subroute == entry.subroute: {}', new_subroute == entry.subroute)
                    entry.subroute = new_subroute
                    entry.queue.clear()
                    entry.queue = collections.deque()
                    for location in new_subroute:
                        entry.queue.append(location)
            elif len(new_subroute) == 0:
                logger.info("New subroute of {} is empty...", origin)
                entry.subroute = new_subroute
                entry.queue.clear()
                entry.queue = collections.deque()
                for location in new_subroute:
                    entry.queue.append(location)
            elif len(entry.subroute) > len(new_subroute) > 0:
                logger.debug("{}'s subroute is longer than it should be now (maybe a worker has been "
                             "added)", origin)
                # we apparently have added at least a worker...
                #   1) reduce the start of the current queue to start of new route
                #   2) append the coords missing (check end of old routelength,
                #      add/remove from there on compared to new)
                old_queue: collections.deque = collections.deque(entry.queue)
                while len(old_queue) > 0 and len(new_subroute) > 0 and old_queue.popleft() != \
                        new_subroute[0]:
                    pass

                if len(old_queue) == 0:
                    logger.debug("{}'s queue is empty, we can just pass him the new subroute", origin)
                    # just set new route...
                    entry.queue = collections.deque()
                    for location in new_subroute:
                        entry.queue.append(location)
                else:
                    # we now are at a point where we need to also check the end of the old queue and
                    # append possibly missing coords to it
                    logger.debug("Checking if the last element of the old queue is present in new "
                                 "subroute")
                    last_el_old_q: Location = old_queue[len(old_queue) - 1]
                    if last_el_old_q in new_subroute:
                        # we have the last element in the old subroute, we can actually append stuff with the
                        # diff to the new route
                        logger.debug("Last element of old queue is present in new subroute, appending the "
                                     "rest of the new subroute to the queue")
                        new_subroute_copy = collections.deque(new_subroute)
                        while len(new_subroute_copy) > 0 and new_subroute_copy.popleft() != last_el_old_q:
                            pass
                        logger.debug("Length of subroute to be extended by {}", len(new_subroute_copy))
                        # replace queue with old_queue
                        entry.queue.clear()
                        entry.queue = old_queue
                        while len(new_subroute_copy) > 0:
                            entry.queue.append(new_subroute_copy.popleft())
                    else:
                        # clear old route and replace with new_subroute
                        # maybe the worker jumps a wider distance
                        logger.debug("Subroute of {} has changed. Replacing entirely", origin)
                        entry.queue.clear()
                        new_subroute_copy = collections.deque(new_subroute)
                        while len(new_subroute_copy) > 0:
                            entry.queue.append(new_subroute_copy.popleft())

            elif len(new_subroute) > len(entry.subroute) > 0:
                #   old routelength < new len(route)/n:
                #   we have likely removed a worker and need to redistribute
                #   1) fetch start and end of old queue
                #   2) we sorta ignore start/what's been visited so far
                #   3) if the end is not part of the new route, check for the last coord of the current route
                #   still in the new route, remove the old rest of it (or just fetch the first coord of the
                #   next subroute and remove the coords of that coord onward)
                logger.debug("A worker has apparently been removed from the routepool")
                last_el_old_route: Location = entry.subroute[len(entry.subroute) - 1]
                old_queue_list: List[Location] = list(entry.queue)
                old_queue: collections.deque = collections.deque(entry.queue)

                last_el_new_route: Location = new_subroute[len(new_subroute) - 1]
                # check last element of new subroute:
                if last_el_new_route is not None and last_el_new_route in old_queue_list:
                    # if in current queue, remove from end of new subroute to end of old queue
                    logger.debug("Last element of new subroute is in old queue, removing everything after "
                                 "that element")
                    del old_queue_list[old_queue.index(last_el_new_route): len(old_queue_list) - 1]
                elif last_el_old_route in new_subroute:
                    # append from end of queue (compared to new subroute) to end of new subroute
                    logger.debug("Last element of old queue in new subroute, appending everything "
                                 "afterwards")
                    missing_new_route_part: List[Location] = new_subroute.copy()
                    del missing_new_route_part[0: new_subroute.index(last_el_old_route)]
                    old_queue_list.extend(missing_new_route_part)

                else:
                    logger.debug("Worker {} getting a completely new route - replace it", origin)
                    new_subroute_copy = collections.deque(new_subroute)
                    old_queue_list.clear()
                    while len(new_subroute_copy) > 0:
                        entry.queue.append(new_subroute_copy.popleft())

                entry.queue = collections.deque()
                [entry.queue.append(i) for i in old_queue_list]

            if len(entry.queue) == 0:
                [entry.queue.append(i) for i in new_subroute]
            # don't forget to update the subroute ;)
            entry.subroute = new_subroute

            if less_coords:
                new_subroute_length = 0

        logger.debug("Done updating subroutes")
        return True
        # TODO: A worker has been removed or added, we need to update the individual workerpools/queues
        #
        # First: Split the original route by the remaining workers => we have a list of new subroutes of
        # len(route)/n coordinates
        #
        # Iterate over all remaining routepools
        # Possible situations now:
        #
        #   Routelengths == new len(route)/n:
        #   Apparently nothing has changed...
        #
        #   old routelength > new len(route)/n:
        #   we have likely added a worker and need to redistribute
        #   1) reduce the start of the current queue to start after the end of the previous pool
        #   2) append the coords missing (check end of old routelength, add/remove from there on compared to new)

        #
        #   old routelength < new len(route)/n:
        #   we have likely removed a worker and need to redistribute
        #   1) fetch start and end of old queue
        #   2) we sorta ignore start/what's been visited so far
        #   3) if the end is not part of the new route, check for the last coord of the current route still in
        #   the new route, remove the old rest of it (or just fetch the first coord of the next subroute and
        #   remove the coords of that coord onward)

    def get_route_status(self, origin) -> Tuple[int, int]:
        if self._route and origin in self._routepool:
            entry: RoutePoolEntry = self._routepool[origin]
            return len(entry.subroute) - len(entry.queue), len(entry.subroute)
        return 1, 1

    def get_rounds(self, origin: str) -> int:
        return self._get_worker_rounds_run_through()

    def get_registered_workers(self) -> Set[str]:
        return self._workers_registered

    def get_position_type(self, origin: str) -> Optional[PositionType]:
        routepool_entry: RoutePoolEntry = self._routepool.get(origin)
        return routepool_entry.last_position_type if routepool_entry else None

    def get_geofence_helper(self) -> GeofenceHelper:
        return self.geofence_helper

    def get_mode(self) -> WorkerType:
        return self._mode

    def get_settings(self) -> Optional[SettingsArea]:
        return self._settings

    def get_current_route(self) -> Tuple[list, Dict[str, RoutePoolEntry]]:
        return self._route, self._routepool

    def get_current_prioroute(self) -> List[RoutePriorityQueueEntry]:
        if self._prio_queue:
            return self._prio_queue.get_copy_of_prioq()
        else:
            return []

    def is_level_mode(self) -> bool:
        return False

    def get_calc_type(self):
        return self._calctype

    def redo_stop_immediately(self, worker, lat: float, lon: float):
        logger.info('redo a unprocessed Stop ({}, {})', lat, lon)
        if worker in self._routepool:
            self._routepool[worker].prio_coord = Location(lat, lon)
            return True
        return False

    def redo_stop_at_end(self, worker: str, location: Location):
        logger.info('Redo an unprocessed location at the end of the route of {} ({})', worker, location)
        if worker in self._routepool:
            self._routepool[worker].queue.append(location)
        if self._delete_coord_after_fetch():
            self._current_route_round_coords.append(location)

    def set_worker_startposition(self, worker, lat: float, lon: float):
        logger.info("Getting startposition ({} / {})", lat, lon)
        if worker not in self._worker_start_position:
            self._worker_start_position[worker] = Location(0.0, 0.0)

        self._worker_start_position[worker] = Location(lat, lon)

    def get_routecalc_id(self) -> Optional[int]:
        return getattr(self._settings, "routecalc", None)

    def _remove_deprecated_prio_events(self) -> bool:
        """
        Whether the Route may remove deprecated coords (e.g. iv_mitm currently does not hold the necessary data for that)
        Returns:
        """
        return True

    def _may_update_routepool(self):
        """
        Whether the routepool may be updated upon finishing routes or a breakup should occur (e.g. iv_mitm)
        Returns: Defaults to True

        """
        return self._mode != WorkerType.IDLE

    def get_quest_layer_to_scan(self) -> Optional[int]:
        """
        Returns: Quest layer to scan (if any)

        """
        return None
