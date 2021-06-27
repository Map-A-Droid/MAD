import asyncio
import collections
import concurrent.futures
import heapq
import math
import time
from abc import ABC, abstractmethod
from asyncio import Task
from datetime import datetime
from enum import IntEnum
from operator import itemgetter
from threading import Thread
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
from dataclasses import dataclass

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.model import SettingsArea, SettingsRoutecalc
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.route.routecalc.ClusteringHelper import ClusteringHelper
from mapadroid.route.routecalc.RoutecalcUtil import RoutecalcUtil
from mapadroid.utils.collections import Location
from mapadroid.utils.geo import get_distance_of_two_points_in_meters
from mapadroid.utils.walkerArgs import parse_args
from mapadroid.worker.WorkerType import WorkerType
from loguru import logger

args = parse_args()

Relation = collections.namedtuple(
    'Relation', ['other_event', 'distance', 'timedelta'])


class PositionType(IntEnum):
    NORMAL = 0,
    PRIO = 1



@dataclass
class RoutePoolEntry:
    last_access: float
    queue: collections.deque
    subroute: List[Location]
    time_added: float
    rounds: int = 0
    current_pos: Location = Location(0.0, 0.0)
    prio_coords: Optional[Location] = None
    worker_sleeping: float = 0
    last_position_type: PositionType = PositionType.NORMAL


class RouteManagerBase(ABC):
    def __init__(self, db_wrapper: DbWrapper, area: SettingsArea, coords: Optional[List[Location]],
                 max_radius: float,
                 max_coords_within_radius: int,
                 geofence_helper: GeofenceHelper,
                 routecalc: SettingsRoutecalc,
                 use_s2: bool = False, s2_level: int = 15,
                 joinqueue=None, mon_ids_iv: Optional[List[int]] = None):
        if mon_ids_iv is None:
            mon_ids_iv = []

        self.db_wrapper: DbWrapper = db_wrapper
        # self.init: bool = area.init if area.mode in ("mon_mitm", "raids_mitm", "pokestop") and area.init else False
        self.init: bool = False
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
        self._is_started: bool = False
        self._first_started = False
        self._current_route_round_coords: List[Location] = []
        self._start_calc: bool = False
        self._coords_to_be_ignored = set()
        # self._level = area.level if area.mode == "pokestop" else False
        # self._calctype = area.route_calc_algorithm if area.mode == "pokestop" else "route"
        self._level = False
        self._calctype = "route"
        self._overwrite_calculation: bool = False
        self._stops_not_processed: Dict[Location, int] = {}
        self._routepool: Dict[str, RoutePoolEntry] = {}
        self._roundcount: int = 0
        self._joinqueue = joinqueue
        self._worker_start_position: Dict[str] = {}
        self._manager_mutex: asyncio.Lock = asyncio.Lock()
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
        self.init_mode_rounds: int = 1
        self._mon_ids_iv: List[int] = mon_ids_iv
        # initialize priority queue variables
        self._prio_queue: Optional[List] = None
        self._update_prio_queue_thread = None
        self._check_routepools_thread: Optional[Task] = None
        self._stop_update_thread: asyncio.Event = asyncio.Event()

    @classmethod
    async def create(cls, db_wrapper: DbWrapper, area: SettingsArea, coords: Optional[List[Location]],
                     max_radius: float,
                     max_coords_within_radius: int,
                     geofence_helper: GeofenceHelper,
                     routecalc: SettingsRoutecalc,
                     use_s2: bool = False, s2_level: int = 15,
                     joinqueue=None, mon_ids_iv: Optional[List[int]] = None):
        self = RouteManagerBase
        if mon_ids_iv is None:
            mon_ids_iv = []

    def get_ids_iv(self) -> List[int]:
        return self._mon_ids_iv

    def get_max_radius(self):
        return self._max_radius

    async def _start_check_routepools(self):
        # TODO: Transform to asyncio
        loop = asyncio.get_running_loop()
        self._check_routepools_thread: Task = loop.create_task(self._check_routepools())

    async def join_threads(self):
        logger.info("Shutdown Route Threads")
        # TODO: Refactor from thread to asyncio task
        if self._update_prio_queue_thread is not None:
            while not self._update_prio_queue_thread.done():
                await asyncio.sleep(1)
                logger.debug("Shutdown Prio Queue Thread - waiting...")
                self._update_prio_queue_thread.cancel()
        logger.debug("Shutdown Prio Queue Thread - done...")
        if self._check_routepools_thread is not None:
            while self._check_routepools_thread.isAlive():
                await asyncio.sleep(1)
                logger.debug("Shutdown Routepool Thread - waiting...")
                self._check_routepools_thread.join(5)

        self._update_prio_queue_thread: Optional[Task] = None
        self._check_routepools_thread = None
        self._stop_update_thread.clear()
        logger.info("Shutdown Route Threads completed")

    async def stop_routemanager(self, joinwithqueue=True):
        # call routetype stoppper
        if self._joinqueue is not None and joinwithqueue:
            logger.info("Adding route to queue")
            await self._joinqueue.set_queue(self.name)

        self._quit_route()
        self._stop_update_thread.set()

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

    def register_worker(self, worker_name) -> bool:
        if worker_name in self._workers_registered:
            logger.info("already registered")
            return False
        else:
            logger.info("registering to routemanager")
            self._workers_registered.add(worker_name)
            return True

    async def unregister_worker(self, worker_name, remove_routepool_entry: bool = False):
        if worker_name in self._workers_registered:
            logger.info("unregistering from routemanager")
            self._workers_registered.remove(worker_name)
        else:
            logger.info("failed unregistering from routemanager since subscription was previously lifted")
        if remove_routepool_entry and worker_name in self._routepool:
            logger.info("Deleting old routepool of {}", worker_name)
            del self._routepool[worker_name]
        if len(self._workers_registered) == 0 and self._is_started:
            logger.info("Routemanager does not have any subscribing workers anymore, calling stop", self.name)
            await self.stop_routemanager()

    async def _start_priority_queue(self):
        if (self.delay_after_timestamp_prio is not None or self._mode == WorkerType.IV_MITM) \
                and not self._mode == WorkerType.STOPS:
            if self._stop_update_thread.is_set():
                self._stop_update_thread.clear()
            self._prio_queue = []
            if self._mode not in [WorkerType.IV_MITM, WorkerType.STOPS]:
                self.clustering_helper = ClusteringHelper(self._max_radius,
                                                          self._max_clustering,
                                                          self._cluster_priority_queue_criteria())
            loop = asyncio.get_event_loop()
            self._update_prio_queue_thread = loop.create_task(self._update_priority_queue_loop())
            logger.info("Started PrioQ")

    # list_coords is a numpy array of arrays!
    def _add_coords_numpy(self, list_coords: np.ndarray):
        fenced_coords = self.geofence_helper.get_geofenced_coordinates(
            list_coords)
        if self._coords_unstructured is None:
            self._coords_unstructured = fenced_coords
        else:
            self._coords_unstructured = np.concatenate(
                (self._coords_unstructured, fenced_coords))

    def add_coords_list(self, list_coords: List[Location]):
        to_be_appended = np.zeros(shape=(len(list_coords), 2))
        for i in range(len(list_coords)):
            to_be_appended[i][0] = float(list_coords[i].lat)
            to_be_appended[i][1] = float(list_coords[i].lng)
        self._add_coords_numpy(to_be_appended)

    # TODO: Really go async or just use threading in routemanagers and make all calls towards it async in executors?
    async def _calculate_new_route(self, coords: List[Location], max_radius, max_coords_within_radius, delete_old_route,
                                   num_procs=0,
                                   in_memory=False, calctype=None):
        if calctype is None:
            calctype = self._calctype
        if coords:
            if self._overwrite_calculation:
                calctype = 'route'

            async with self.db_wrapper as session, session:
                new_route = await RoutecalcUtil.get_json_route(session, self._routecalc.routecalc_id, coords,
                                                               max_radius, max_coords_within_radius, in_memory,
                                                               num_processes=num_procs,
                                                               algorithm=calctype, use_s2=self.useS2,
                                                               s2_level=self.S2level,
                                                               route_name=self.name, delete_old_route=delete_old_route)
            if self._overwrite_calculation:
                self._overwrite_calculation = False
            return new_route
        return []

    async def initial_calculation(self, max_radius: float, max_coords_within_radius: int, num_procs: int = 1,
                                  delete_old_route: bool = False):
        if not self._routecalc.routefile:
            await self.recalc_route(max_radius, max_coords_within_radius, num_procs,
                                    delete_old_route=delete_old_route,
                                    in_memory=True,
                                    calctype='quick')
            # Route has not previously been calculated.  Recalculate a quick route then calculate the optimized route
            # TODO: Executor
            args = (self._max_radius, self._max_coords_within_radius)
            kwargs = {
                'num_procs': 0
            }
            Thread(target=self.recalc_route_adhoc, args=args, kwargs=kwargs).start()
        else:
            await self.recalc_route(max_radius, max_coords_within_radius, num_procs=0, delete_old_route=False)

    async def recalc_route(self, max_radius: float, max_coords_within_radius: int, num_procs: int = 1,
                           delete_old_route: bool = False, in_memory: bool = False, calctype: str = None):
        async with self._manager_mutex:
            current_coords = self._coords_unstructured
            new_route = await self._calculate_new_route(current_coords, max_radius, max_coords_within_radius,
                                                        delete_old_route, num_procs,
                                                        in_memory=in_memory,
                                                        calctype=calctype)
            self._route.clear()
            for coord in new_route:
                self._route.append(Location(coord["lat"], coord["lng"]))
            self._current_route_round_coords = self._route.copy()
            return new_route

    async def recalc_route_adhoc(self, max_radius: float, max_coords_within_radius: int, num_procs: int = 1,
                                 active: bool = False, calctype: str = 'route'):
        async with self._manager_mutex:
            self._clear_coords()
            coords = await self._get_coords_post_init()
            self.add_coords_list(coords)
            new_route = await self.recalc_route(max_radius, max_coords_within_radius, num_procs,
                                                in_memory=True,
                                                calctype=calctype)
            calc_coords = []
            for coord in new_route:
                calc_coords.append('%s,%s' % (coord['lat'], coord['lng']))
            async with self.db_wrapper as session, session:
                await session.merge(self._routecalc)
                self._routecalc.routefile = str(calc_coords).replace("\'", "\"")
                self._routecalc.last_updated = datetime.utcnow()
                # TODO: First update the resource or simply set using helper which fetches the object first?
                await session.flush([self._routecalc])
                await session.commit()
            connected_worker_count = len(self._workers_registered)
            if connected_worker_count > 0:
                for worker in self._workers_registered.copy():
                    await self.unregister_worker(worker, True)
            else:
                await self.stop_routemanager()

    async def _update_priority_queue_loop(self):
        if self._priority_queue_update_interval() is None or self._priority_queue_update_interval() == 0:
            return
        while not self._stop_update_thread.is_set():
            # retrieve the latest hatches from DB
            new_queue = await self._retrieve_latest_priority_queue()
            await self._merge_priority_queue(new_queue)
            redocounter = 0
            while redocounter <= self._priority_queue_update_interval() and not self._stop_update_thread.is_set():
                redocounter += 1
                await asyncio.sleep(1)
                if self._stop_update_thread.is_set():
                    logger.info("Kill Prio Queue loop while sleeping")
                    break

    async def _merge_priority_queue(self, new_queue):
        if new_queue is not None:
            new_queue = list(new_queue)
            logger.info("Got {} new events", len(new_queue))
            # TODO: verify if this procedure is good for other modes, too
            # TODO: Async Executor as clustering takes time..
            if self._mode == WorkerType.MON_MITM:
                new_queue = await self._filter_priority_queue_internal(new_queue)
                logger.debug2("Merging existing Q of {} events with {} clustered new events",
                                   len(self._prio_queue), len(new_queue))
                merged: List[Tuple[int, Location]] = list(set(new_queue + self._prio_queue))
                merged = list(merged)
                logger.info("Merging resulted in queue with {} entries", len(merged))
                merged = await self._filter_priority_queue_internal(merged, cluster=False)
            else:
                merged = await self._filter_priority_queue_internal(new_queue)
            heapq.heapify(merged)
            self._prio_queue = merged
            logger.info("Finalized new priority queue with {} entries", len(merged))
            logger.debug2("Priority queue entries: {}", str(merged))

    def date_diff_in_seconds(self, dt2, dt1):
        timedelta = dt2 - dt1
        return timedelta.days * 24 * 3600 + timedelta.seconds

    def dhms_from_seconds(self, seconds):
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return hours, minutes, seconds

    def _get_round_finished_string(self):
        round_finish_time = datetime.now()
        round_completed_in = ("%d hours, %d minutes, %d seconds" % (self.dhms_from_seconds(self.date_diff_in_seconds(
            round_finish_time,
            self._round_started_time))))
        return round_completed_in

    def add_coord_to_be_removed(self, lat: float, lon: float):
        if lat < -90.0 or lat > 90.0 or lon < -180.0 or lon > 180.0:
            return
        self._coords_to_be_ignored.add(Location(lat, lon))

    @abstractmethod
    async def _retrieve_latest_priority_queue(self) -> List[Tuple[int, Location]]:
        """
        Method that's supposed to return a plain list containing (timestamp, Location) of the next events of interest
        :return:
        """
        pass

    @abstractmethod
    async def start_routemanager(self):
        """
        Starts priority queue or whatever the implementations require
        :return:
        """
        pass

    @abstractmethod
    def _quit_route(self):
        """
        Killing the Route Thread
        :return:
        """
        pass

    @abstractmethod
    async def _get_coords_post_init(self) -> List[Location]:
        """
        Return list of coords to be fetched and used for routecalc
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
    async def _recalc_route_workertype(self):
        """
        Return a new route for worker
        :return:
        """
        pass

    @abstractmethod
    async def _get_coords_after_finish_route(self) -> bool:
        """
        :return:
        """
        pass

    @abstractmethod
    def _cluster_priority_queue_criteria(self):
        """
        If you do not want to have any filtering, simply return 0, 0, otherwise simply
        return timedelta_seconds, distance
        :return:
        """

    @abstractmethod
    def _priority_queue_update_interval(self):
        """
        The time to sleep in between consecutive updates of the priority queue
        :return:
        """

    @abstractmethod
    def _delete_coord_after_fetch(self) -> bool:
        """
        Whether coords fetched from get_next_location should be removed from the total route
        :return:
        """

    async def _filter_priority_queue_internal(self, latest, cluster=True) -> List[Tuple[int, Location]]:
        """
        Filter through the internal priority queue and cluster events within the timedelta and distance returned by
        _cluster_priority_queue_criteria
        :return:
        """
        if self._mode == WorkerType.IV_MITM:
            # exclude IV prioQ to also pass encounterIDs since we do not pass additional information through when
            # clustering
            return latest
        if self._mode == WorkerType.MON_MITM and self.remove_from_queue_backlog == 0:
            logger.warning("You are running in mon_mitm mode with priority queue enabled and "
                                "remove_from_queue_backlog set to 0. This may result in building up a significant "
                                "queue "
                                "backlog and reduced scanning performance. Please review this setting or set it to "
                                "the "
                                "default of 300.")

        if self.remove_from_queue_backlog is not None:
            delete_before = time.time() - self.remove_from_queue_backlog
        else:
            delete_before = 0
        if self._mode == WorkerType.MON_MITM:
            delete_after = time.time() + 600
            latest = [to_keep for to_keep in latest if
                      not to_keep[0] < delete_before and not to_keep[0] > delete_after]
        else:
            latest = [to_keep for to_keep in latest if not to_keep[0] < delete_before]
        # TODO: sort latest by modified flag of event
        if cluster:
            loop = asyncio.get_running_loop()
            with concurrent.futures.ThreadPoolExecutor() as pool:
                merged = await loop.run_in_executor(
                    pool, self.clustering_helper.get_clustered, (latest,))
            # merged = self.clustering_helper.get_clustered(latest)
            return merged
        else:
            return latest

    def __set_routepool_entry_location(self, origin: str, pos: Location):
        if self._routepool.get(origin, None) is not None:
            self._routepool[origin].current_pos = pos
            self._routepool[origin].last_access = time.time()
            self._routepool[origin].worker_sleeping = 0

    async def get_next_location(self, origin: str) -> Optional[Location]:
        logger.debug4("get_next_location called")
        if not self._is_started:
            logger.info("Starting routemanager in get_next_location")
            if not await self.start_routemanager():
                logger.info('No coords available - quit worker')
                return None

        if self._start_calc:
            logger.info("Another process already calculate the new route")
            return None

        if origin not in self._workers_registered:
            self.register_worker(origin)

        routepool_entry: RoutePoolEntry = self._routepool.get(origin, None)
        if not routepool_entry:
            logger.debug("No subroute/routepool entry present, creating it")
            routepool_entry = RoutePoolEntry(time.time(), collections.deque(), [], time_added=time.time())
            self._routepool[origin] = routepool_entry
            if origin in self._worker_start_position:
                routepool_entry.current_pos = self._worker_start_position[origin]
            if not self._worker_changed_update_routepools():
                logger.info("Failed updating routepools after adding a worker to it")
                return None
        elif routepool_entry.prio_coords and self._mode != WorkerType.IV_MITM:
            prioevent = routepool_entry.prio_coords
            routepool_entry.prio_coords = None
            logger.info('getting a nearby prio event {}', prioevent)
            self.__set_routepool_entry_location(origin, prioevent)
            routepool_entry.last_position_type = PositionType.PRIO
            return prioevent

        # first check if a location is available, if not, block until we have one...

        # check priority queue for items of priority that are past our time...
        # if that is not the case, simply increase the index in route and return the location on route

        # determine whether we move to the next location or the prio queue top's item
        # TODO: Better use a strategy pattern or observer for extendability?
        if self.delay_after_timestamp_prio and (not routepool_entry.last_position_type == PositionType.PRIO
                                                or self.starve_route):
            # Check the PrioQ
            try:
                next_timestamp, next_coord = None, None
                if self._mode == WorkerType.IV_MITM:
                    # "blocking" to wait for a coord
                    while not next_timestamp:
                        try:
                            next_timestamp, next_coord = heapq.heappop(self._prio_queue)
                        except IndexError:
                            # No item available yet, sleep
                            await asyncio.sleep(1)
                else:
                    next_timestamp, next_coord = heapq.heappop(self._prio_queue)
                next_readable_time = datetime.fromtimestamp(next_timestamp).strftime('%Y-%m-%d %H:%M:%S')
                if next_timestamp < time.time():
                    raise IndexError("Next event at {} has not taken place yet", next_readable_time)
                if self._mode == WorkerType.MON_MITM:
                    if self.remove_from_queue_backlog not in [None, 0]:
                        delete_before = time.time() - self.remove_from_queue_backlog
                    else:
                        delete_before = 0

                    while next_timestamp < delete_before:
                        # TODO: Move task_done elsewhere?
                        next_timestamp, next_coord = heapq.heappop(self._prio_queue)
                        next_readable_time = datetime.fromtimestamp(next_timestamp).strftime('%Y-%m-%d %H:%M:%S')
                        if next_timestamp < delete_before:
                            logger.warning(
                                "Prio event surpassed the maximum backlog time and will be skipped. Make "
                                "sure you run enough workers or reduce the size of the area! (event was "
                                "scheduled for {})", next_readable_time)

                while (not self._check_coord_and_remove_from_route_if_applicable(next_coord, origin)
                       or self._other_worker_closer_to_prioq(next_coord, origin)):
                    logger.info("Invalid prio event or scheduled for {} passed to a closer worker.",
                                      next_readable_time)
                    next_timestamp, next_coord = heapq.heappop(self._prio_queue)

                routepool_entry.last_position_type = PositionType.PRIO
                logger.debug2("Moving to {}, {} for a priority event scheduled for {}", next_coord.lat,
                                  next_coord.lng, next_readable_time)
                self.__set_routepool_entry_location(origin, next_coord)
                return next_coord
            except IndexError:
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
            self._round_started_time = datetime.now()
            if len(self._route) == 0:
                return None
            logger.info("Round started at {}", self._round_started_time)
        elif self._round_started_time is None:
            self._round_started_time = datetime.now()

        if len(routepool_entry.queue) == 0:
            # worker done with his subroute
            routepool_entry.rounds += 1

        # Check if we are in init:
        if self.init and self._get_worker_rounds_run_through() >= self.init_mode_rounds and \
                len(routepool_entry.queue) == 0:
            # we are done with init, let's calculate a new route
            logger.warning("Init done, it took {}, calculating new route...",
                                self._get_round_finished_string())
            if self._start_calc:
                logger.info("Another process already calculate the new route")
                return None
            self._start_calc = True
            self._clear_coords()
            coords = await self._get_coords_post_init()
            logger.debug("Setting {} coords to as new points ", len(coords))
            self.add_coords_list(coords)
            logger.debug("Route being calculated")
            await self._recalc_route_workertype()
            self.init = False
            await self._change_init_mapping()
            self._start_calc = False
            logger.debug("Initroute is finished - restart worker")
            return None

        elif len(self._current_route_round_coords) >= 0 and len(routepool_entry.queue) == 0:
            # only quest could hit this else!
            logger.info("finished subroute, updating all subroutes if necessary")

            if self._mode == WorkerType.STOPS and not self.init:
                # check for coords not in other workers to get a real open coord list
                if not self._get_coords_after_finish_route():
                    logger.info("No more coords available - dont update routepool")
                    return None

            if not self._worker_changed_update_routepools():
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
            if self._delete_coord_after_fetch() and next_coord in self._current_route_round_coords \
                    and not self.init:
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

        current_worker_pos = self._routepool[origin].current_pos
        distance_worker = get_distance_of_two_points_in_meters(current_worker_pos.lat, current_worker_pos.lng,
                                                               prioqcoord.lat, prioqcoord.lng)

        logger.debug("distance to PrioQ {}: {}", prioqcoord, distance_worker)
        temp_distance = distance_worker

        for worker in self._routepool.keys():
            if worker == origin or self._routepool[worker].prio_coords \
                    or self._routepool[origin].last_position_type == PositionType.PRIO:
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
            self._routepool[closer_worker].prio_coords = prioqcoord
            logger.debug("Worker {} is closer to PrioQ event {}", closer_worker, prioqcoord)
            return True

        logger.debug("No Worker is closer to PrioQ event {}", prioqcoord)

        return False

    # to be called regularly to remove inactive workers that used to be registered
    async def _check_routepools(self, timeout: int = 300):
        while not self._stop_update_thread.is_set():
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

    def _worker_changed_update_routepools(self):
        less_coords: bool = False
        workers: int = 0
        if not self._is_started:
            return True
        if self._mode not in (WorkerType.IV_MITM, WorkerType.IDLE) and len(self._current_route_round_coords) == 0:
            logger.info("No more coords - breakup")
            return False
        if self._mode in (WorkerType.IV_MITM, WorkerType.IDLE):
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

            logger.debug("New Subroute for worker {}: {}", origin, new_subroute)
            logger.debug("Old Subroute for worker {}: {}", origin, entry.subroute)

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
                    logger.debug('new_subroute: {}', new_subroute)
                    logger.debug('entry.subroute: {}', entry.subroute)
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

        logger.debug("Current routepool: {}", self._routepool)
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

    @abstractmethod
    async def _change_init_mapping(self) -> None:
        """
        Used to adjust the init flag of areas if applicable...
        """
        pass

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

    def get_geofence_helper(self) -> Optional[GeofenceHelper]:
        return self.geofence_helper

    def get_init(self) -> bool:
        return self.init

    def get_mode(self) -> WorkerType:
        return self._mode

    def get_settings(self) -> Optional[SettingsArea]:
        return self._settings

    def get_current_route(self) -> Tuple[list, Dict[str, RoutePoolEntry]]:
        return self._route, self._routepool

    def get_current_prioroute(self) -> List[Location]:
        return self._prio_queue

    def get_level_mode(self):
        return self._level

    def get_calc_type(self):
        return self._calctype

    def redo_stop(self, worker, lat, lon):
        logger.info('redo a unprocessed Stop ({}, {})', lat, lon)
        if worker in self._routepool:
            self._routepool[worker].prio_coords = Location(lat, lon)
            return True
        return False

    def set_worker_startposition(self, worker, lat, lon):
        logger.info("Getting startposition ({} / {})", lat, lon)
        if worker not in self._worker_start_position:
            self._worker_start_position[worker] = Location(0.0, 0.0)

        self._worker_start_position[worker] = Location(lat, lon)
