import collections
import heapq
import json
import math
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from threading import Event, Lock, RLock, Thread
from typing import Dict, List, Optional, Tuple
from queue import Queue, Empty

import numpy as np

from db.dbWrapperBase import DbWrapperBase
from geofence.geofenceHelper import GeofenceHelper
from route.routecalc.ClusteringHelper import ClusteringHelper
from route.routecalc.calculate_route import getJsonRoute
from utils.collections import Location
from utils.logging import logger
from utils.walkerArgs import parseArgs
from utils.geo import get_distance_of_two_points_in_meters
from operator import itemgetter

args = parseArgs()

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
    has_prio_event: bool = False
    prio_coords: Location = Location(0.0, 0.0)
    worker_sleeping: float = 0
    last_round_prio_event: bool = False


class RouteManagerBase(ABC):
    def __init__(self, db_wrapper: DbWrapperBase, coords: List[Location], max_radius: float,
                 max_coords_within_radius: int, path_to_include_geofence: str, path_to_exclude_geofence: str,
                 routefile: str, mode=None, init: bool = False, name: str = "unknown", settings: dict = None,
                 level: bool = False, calctype: str = "optimized", joinqueue = None):
        self.db_wrapper: DbWrapperBase = db_wrapper
        self.init: bool = init
        self.name: str = name
        self._coords_unstructured: List[Location] = coords
        self.geofence_helper: GeofenceHelper = GeofenceHelper(
            path_to_include_geofence, path_to_exclude_geofence)
        self._routefile = os.path.join(args.file_path, routefile)
        self._max_radius: float = max_radius
        self._max_coords_within_radius: int = max_coords_within_radius
        self.settings: dict = settings
        self.mode = mode
        self._is_started: bool = False
        self._first_started = False
        self._current_route_round_coords: List[Location] = []
        self._start_calc: bool = False
        self._positiontyp = {}
        self._coords_to_be_ignored = set()
        self._level = level
        self._calctype = calctype
        self._overwrite_calculation: bool = False
        self._stops_not_processed: Dict[Location, int] = {}
        self._routepool: Dict[str, RoutePoolEntry] = {}
        self._roundcount: int = 0
        self._joinqueue = joinqueue

        # we want to store the workers using the routemanager
        self._workers_registered: List[str] = []
        self._workers_registered_mutex = RLock()

        # waiting till routepool is filled up
        self._workers_fillup_mutex = RLock()

        self._last_round_prio = {}
        self._manager_mutex = RLock()
        self._round_started_time = None
        self._route: List[Location] = []

        if coords is not None:
            if init:
                fenced_coords = coords
            else:
                fenced_coords = self.geofence_helper.get_geofenced_coordinates(
                    coords)
            new_coords = getJsonRoute(
                fenced_coords, max_radius, max_coords_within_radius, routefile,
                algorithm=calctype)
            for coord in new_coords:
                self._route.append(Location(coord["lat"], coord["lng"]))
        self._current_index_of_route = 0
        self._init_mode_rounds = 0

        if self.settings is not None:
            self.delay_after_timestamp_prio = self.settings.get(
                "delay_after_prio_event", None)
            self.starve_route = self.settings.get("starve_route", False)
        else:
            self.delay_after_timestamp_prio = None
            self.starve_route = False

        # initialize priority queue variables
        self._prio_queue = None
        self._update_prio_queue_thread = None
        self._check_routepools_thread = None
        self._stop_update_thread = Event()

    def get_ids_iv(self) -> Optional[List[int]]:
        if self.settings is not None:
            return self.settings.get("mon_ids_iv_raw", [])
        else:
            return None

    def _start_check_routepools(self):
        self._check_routepools_thread = Thread(name="_check_routepools_" + self.name,
                                               target=self._check_routepools)
        self._check_routepools_thread.daemon = True
        self._check_routepools_thread.start()

    def join_threads(self):
        logger.info("Join Route Threads")
        if self._update_prio_queue_thread is not None:
            while self._update_prio_queue_thread.isAlive():
                time.sleep(1)
                logger.debug("Shutdown Prio Queue Thread - waiting...")
                self._update_prio_queue_thread.join(5)
        logger.debug("Shutdown Prio Queue Thread - done...")
        if self._check_routepools_thread is not None:
            while self._check_routepools_thread.isAlive():
                time.sleep(1)
                logger.debug("Shutdown Routepool Thread - waiting...")
                self._check_routepools_thread.join(5)

        self._update_prio_queue_thread = None
        self._check_routepools_thread = None
        self._stop_update_thread.clear()
        logger.info("Done joining Route Threads")

    def stop_routemanager(self):
        # call routetype stoppper
        self._quit_route()
        self._stop_update_thread.set()

        if self._joinqueue is not None: self._joinqueue.set_queue(self.name)
        logger.info("Shutdown of route {} completed".format(str(self.name)))

    def _init_route_queue(self):
        with self._manager_mutex:
            if len(self._route) > 0:
                self._current_route_round_coords.clear()
                logger.debug("Creating queue for coords")
                for latlng in self._route:
                    self._current_route_round_coords.append(latlng)
                logger.debug("Finished creating queue")

    def _clear_coords(self):
        with self._manager_mutex:
            self._coords_unstructured = None

    def register_worker(self, worker_name) -> bool:
        self._workers_registered_mutex.acquire()
        try:
            if worker_name in self._workers_registered:
                logger.info("Worker {} already registered to routemanager {}", str(
                    worker_name), str(self.name))
                return False
            else:
                logger.info("Worker {} registering to routemanager {}",
                            str(worker_name), str(self.name))
                self._workers_registered.append(worker_name)
                self._positiontyp[worker_name] = 0
                return True

        finally:
            self._workers_registered_mutex.release()

    def unregister_worker(self, worker_name):
        self._workers_registered_mutex.acquire()
        try:
            if worker_name in self._workers_registered:
                logger.info("Worker {} unregistering from routemanager {}", str(
                    worker_name), str(self.name))
                self._workers_registered.remove(worker_name)
                if worker_name in self._routepool:
                    logger.info("Deleting old routepool of {}", str(worker_name))
                    del self._routepool[worker_name]
            else:
                # TODO: handle differently?
                logger.info(
                    "Worker {} failed unregistering from routemanager {} since subscription was previously lifted",
                    str(
                        worker_name), str(self.name))
                if worker_name in self._routepool:
                    logger.info("Deleting old routepool of {}", str(worker_name))
                    del self._routepool[worker_name]
            if len(self._workers_registered) == 0 and self._is_started:
                logger.info(
                    "Routemanager {} does not have any subscribing workers anymore, calling stop", str(self.name))
                self.stop_routemanager()
        finally:
            self._workers_registered_mutex.release()

    def stop_worker(self):
        self._workers_registered_mutex.acquire()
        try:
            for worker in self._workers_registered:
                logger.info("Worker {} stopped from routemanager {}", str(
                    worker), str(self.name))
                worker.stop_worker()
                self._workers_registered.remove(worker)
                if worker in self._routepool:
                    logger.info("Deleting old routepool of {}", str(worker))
                    del self._routepool[worker]
            if len(self._workers_registered) == 0 and self._is_started:
                logger.info(
                    "Routemanager {} does not have any subscribing workers anymore, calling stop", str(self.name))
                self.stop_routemanager()
        finally:
            self._workers_registered_mutex.release()

    def _check_started(self):
        return self._is_started

    def _start_priority_queue(self):
        if (self._update_prio_queue_thread is None and (self.delay_after_timestamp_prio is not None or self.mode ==
                                                        "iv_mitm") and not self.mode == "pokestops"):
            self._prio_queue = []
            if self.mode not in ["iv_mitm", "pokestops"]:
                self.clustering_helper = ClusteringHelper(self._max_radius,
                                                          self._max_coords_within_radius,
                                                          self._cluster_priority_queue_criteria())
            self._update_prio_queue_thread = Thread(name="prio_queue_update_" + self.name,
                                                    target=self._update_priority_queue_loop)
            self._update_prio_queue_thread.daemon = True
            self._update_prio_queue_thread.start()

    # list_coords is a numpy array of arrays!
    def add_coords_numpy(self, list_coords: np.ndarray):
        fenced_coords = self.geofence_helper.get_geofenced_coordinates(
            list_coords)
        with self._manager_mutex:
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
        self.add_coords_numpy(to_be_appended)

    def calculate_new_route(self, coords, max_radius, max_coords_within_radius, routefile, delete_old_route,
                            num_procs=0):
        if self._overwrite_calculation:
            calctype = 'quick'
        else:
            calctype = self._calctype

        if delete_old_route and os.path.exists(str(routefile) + ".calc"):
            logger.debug("Deleting routefile...")
            os.remove(str(routefile) + ".calc")
        new_route = getJsonRoute(coords, max_radius, max_coords_within_radius, num_processes=num_procs,
                                 routefile=routefile, algorithm=calctype)
        if self._overwrite_calculation:
            self._overwrite_calculation = False
        return new_route

    def empty_routequeue(self):
        return len(self._current_route_round_coords) > 0

    def recalc_route(self, max_radius: float, max_coords_within_radius: int, num_procs: int = 1,
                     delete_old_route: bool = False, nofile: bool = False):
        current_coords = self._coords_unstructured
        if nofile:
            routefile = None
        else:
            routefile = self._routefile
        new_route = self.calculate_new_route(current_coords, max_radius, max_coords_within_radius,
                                             routefile, delete_old_route, num_procs)
        with self._manager_mutex:
            self._route.clear()
            for coord in new_route:
                self._route.append(Location(coord["lat"], coord["lng"]))
            self._current_route_round_coords = self._route.copy()
            self._current_index_of_route = 0

    def _update_priority_queue_loop(self):
        if self._priority_queue_update_interval() is None or self._priority_queue_update_interval() == 0:
            return
        while not self._stop_update_thread.is_set():
            # retrieve the latest hatches from DB
            # newQueue = self._db_wrapper.get_next_raid_hatches(self._delayAfterHatch, self._geofenceHelper)
            new_queue = self._retrieve_latest_priority_queue()
            self._merge_priority_queue(new_queue)
            redocounter = 0
            while redocounter <= self._priority_queue_update_interval() and not self._stop_update_thread.is_set():
                redocounter += 1
                time.sleep(1)
                if self._stop_update_thread.is_set():
                    logger.info("Kill Prio Queue loop while sleeping")
                    break

    def _merge_priority_queue(self, new_queue):
        if new_queue is not None:
            with self._manager_mutex:
                merged = list(new_queue)
                logger.info("New raw priority queue with {} entries", len(merged))
                merged = self._filter_priority_queue_internal(merged)
                heapq.heapify(merged)
                self._prio_queue = merged
            logger.info("New clustered priority queue with {} entries", len(merged))
            logger.debug("Priority queue entries: {}", str(merged))

    def date_diff_in_seconds(self, dt2, dt1):
        timedelta = dt2 - dt1
        return timedelta.days * 24 * 3600 + timedelta.seconds

    def dhms_from_seconds(self, seconds):
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        # days, hours = divmod(hours, 24)
        return hours, minutes, seconds

    def _get_round_finished_string(self):
        round_finish_time = datetime.now()
        round_completed_in = (
                "%d hours, %d minutes, %d seconds" % (
            self.dhms_from_seconds(
                self.date_diff_in_seconds(
                    round_finish_time, self._round_started_time)
            )
        )
        )
        return round_completed_in

    def add_coord_to_be_removed(self, lat: float, lon: float):
        if lat < -90.0 or lat > 90.0 or lon < -180.0 or lon > 180.0:
            return
        with self._manager_mutex:
            self._coords_to_be_ignored.add(Location(lat, lon))

    @abstractmethod
    def _retrieve_latest_priority_queue(self):
        """
        Method that's supposed to return a plain list containing (timestamp, Location) of the next events of interest
        :return:
        """
        pass

    @abstractmethod
    def _start_routemanager(self):
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
    def _get_coords_post_init(self):
        """
        Return list of coords to be fetched and used for routecalc
        :return:
        """
        pass

    @abstractmethod
    def _check_coords_before_returning(self, lat, lng):
        """
        Return list of coords to be fetched and used for routecalc
        :return:
        """
        pass

    @abstractmethod
    def _recalc_route_workertype(self):
        """
        Return a new route for worker
        :return:
        """
        pass

    @abstractmethod
    def _get_coords_after_finish_route(self) -> bool:
        """
        Return list of coords to be fetched after finish a route
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

    def _filter_priority_queue_internal(self, latest):
        """
        Filter through the internal priority queue and cluster events within the timedelta and distance returned by
        _cluster_priority_queue_criteria
        :return:
        """
        # timedelta_seconds = self._cluster_priority_queue_criteria()
        if self.mode == "iv_mitm":
            # exclude IV prioQ to also pass encounterIDs since we do not pass additional information through when
            # clustering
            return latest
        delete_seconds_passed = 0
        if self.settings is not None:
            delete_seconds_passed = self.settings.get(
                "remove_from_queue_backlog", 0)

        if delete_seconds_passed is not None:
            delete_before = time.time() - delete_seconds_passed
        else:
            delete_before = 0
        latest = [to_keep for to_keep in latest if not to_keep[0] < delete_before]
        # TODO: sort latest by modified flag of event
        # merged = self._merge_queue(latest, self._max_radius, 2, timedelta_seconds)
        merged = self.clustering_helper.get_clustered(latest)
        return merged

    def __set_routepool_entry_location(self, origin: str, pos: Location):
        with self._manager_mutex:
            if self._routepool.get(origin, None) is not None:
                self._routepool[origin].current_pos = pos
                self._routepool[origin].last_access = time.time()
                self._routepool[origin].worker_sleeping = 0

    def get_next_location(self, origin: str) -> Optional[Location]:
        logger.debug("get_next_location of {} called", str(self.name))

        if not self._is_started:
            logger.info(
                "Starting routemanager {} in get_next_location", str(self.name))
            if not self._start_routemanager():
                logger.info('No coords available - quit worker')
                return None

        if self._start_calc:
            logger.info("Another process already calculate the new route")
            return None

        with self._manager_mutex:
            with self._workers_registered_mutex:
                if origin not in self._workers_registered:
                    self.register_worker(origin)

            if origin not in self._routepool:
                logger.debug("No subroute/routepool entry of {} present, creating it", origin)
                self._routepool[origin] = RoutePoolEntry(time.time(), collections.deque(), [],
                                                         time_added=time.time())
                if not self.__worker_changed_update_routepools():
                    logger.info("Failed updating routepools after adding a worker to it")
                    return None

            elif self._routepool[origin].has_prio_event and self.mode != 'iv_mitm':
                prioevent = self._routepool[origin].prio_coords
                logger.info('Worker {} getting a nearby prio event {}', origin, prioevent)
                self._routepool[origin].has_prio_event = False
                self.__set_routepool_entry_location(origin, prioevent)
                self._routepool[origin].last_round_prio_event = True
                return prioevent

        # first check if a location is available, if not, block until we have one...
        got_location = False
        while not got_location and self._is_started and not self.init:
            logger.debug(
                "{}: Checking if a location is available...", str(self.name))
            with self._manager_mutex:
                got_location = self._prio_queue is not None and len(self._prio_queue) > 0 or self.mode != 'iv_mitm'
                if not got_location: time.sleep(1)

        logger.debug(
            "{}: Location available, acquiring lock and trying to return location", self.name)
        with self._manager_mutex:
            # check priority queue for items of priority that are past our time...
            # if that is not the case, simply increase the index in route and return the location on route

            # determine whether we move to the next location or the prio queue top's item
            if (self.delay_after_timestamp_prio is not None and ((not self._last_round_prio.get(origin, False)
                                                                  or self.starve_route)
                                                                 and self._prio_queue and len(self._prio_queue) > 0
                                                                 and self._prio_queue[0][0] < time.time())):
                logger.debug("{}: Priority event", self.name)
                next_coord = heapq.heappop(self._prio_queue)[1]
                if self._other_worker_closer_to_prioq(next_coord, origin):
                    self._last_round_prio[origin] = True
                    self._positiontyp[origin] = 1
                    return self.get_next_location(origin)
                self._last_round_prio[origin] = True
                self._positiontyp[origin] = 1
                logger.info("Route {} is moving to {}, {} for a priority event",
                            self.name, next_coord.lat, next_coord.lng)
            else:
                logger.debug("{}: Moving on with route", self.name)
                self._positiontyp[origin] = 0
                # TODO: this check is likely always true now.............
                if self.check_worker_rounds() > self._roundcount:
                    self._roundcount = self.check_worker_rounds()
                    if self._round_started_time is not None:
                        logger.info("All subroutes of {} reached the first spot again. It took {}",
                                    self.name, self._get_round_finished_string())
                    self._round_started_time = datetime.now()
                    if len(self._route) == 0:
                        return None
                    logger.info("Round of route {} started at {}",
                                self.name, self._round_started_time)
                elif self._round_started_time is None:
                    self._round_started_time = datetime.now()

                if len(self._routepool[origin].queue) == 0:
                    # worker do the part of route
                    self._routepool[origin].rounds += 1

                # continue as usual
                if self.init and self.check_worker_rounds() >= int(self.settings.get("init_mode_rounds", 1)) and \
                        len(self._routepool[origin].queue) == 0:
                    # we are done with init, let's calculate a new route
                    logger.warning("Init of {} done, it took {}, calculating new route...",
                                   self.name, self._get_round_finished_string())
                    if self._start_calc:
                        logger.info("Another process already calculate the new route")
                        return None
                    self._start_calc = True
                    self._clear_coords()
                    coords = self._get_coords_post_init()
                    logger.debug("Setting {} coords to as new points in route of {}",
                                 len(coords), self.name)
                    self.add_coords_list(coords)
                    logger.debug("Route of {} is being calculated", self.name)
                    self._recalc_route_workertype()
                    self.init = False
                    self.change_init_mapping(self.name)
                    self._start_calc = False
                    logger.debug("Initroute of {} is finished - restart worker", self.name)
                    return None

                elif len(self._current_route_round_coords) >= 0 and len(self._routepool[origin].queue) == 0:
                    # only quest could hit this else!
                    logger.info("Worker finished his subroute, updating all subroutes if necessary")

                    if self.mode == 'pokestops' and not self.init:
                        # check for coords not in other workers to get a real open coord list
                        if not self._get_coords_after_finish_route():
                            logger.info("No more coords available - dont update routepool")
                            return None

                    if not self.__worker_changed_update_routepools():
                        logger.info("Failed updating routepools ...")
                        return None

                    if len(self._routepool[origin].queue) == 0 and len(self._routepool[origin].subroute) == 0:
                        logger.info("Subroute-update won't help or queue and subroute are empty, "
                                    "signalling worker to reconnect")
                        self._routepool[origin].last_access = time.time()
                        return None
                    elif len(self._routepool[origin].queue) == 0 and len(self._routepool[origin].subroute) > 0:
                        [self._routepool[origin].queue.append(i) for i in self._routepool[origin].subroute]
                    elif len(self._routepool[origin].queue) > 0 and len(self._routepool[origin].subroute) > 0:
                        logger.info("Getting new coords for route {}", str(self.name))
                    else:
                        logger.info("Not getting new coords - leaving worker")
                        return None

                if len(self._routepool[origin].queue) == 0:
                    logger.warning("Having updated routepools and checked lengths of queue and subroute, "
                                   "{}'s queue is still empty, signalling worker to stop whatever he is doing",
                                   self.name)
                    self._routepool[origin].last_access = time.time()
                    return None

                next_coord = self._routepool[origin].queue.popleft()
                if self._delete_coord_after_fetch() and next_coord in self._current_route_round_coords \
                        and not self.init:
                    self._current_route_round_coords.remove(next_coord)
                logger.info("{}: Moving on with location {} [{} coords left (Workerpool)]",
                            str(self.name), str(next_coord), str(len(self._routepool[origin].queue)))

                self._last_round_prio[origin] = False
                self._routepool[origin].last_round_prio_event = False
            logger.debug("{}: Done grabbing next coord, releasing lock and returning location: {}", str(
                self.name), str(next_coord))
            if self._check_coords_before_returning(next_coord.lat, next_coord.lng):

                if self._delete_coord_after_fetch() and next_coord in self._current_route_round_coords \
                        and not self.init:
                    self._current_route_round_coords.remove(next_coord)

                self.__set_routepool_entry_location(origin, next_coord)

                return next_coord
            else:
                return self.get_next_location(origin)

    def check_worker_rounds(self) -> int:
        temp_worker_round_list: list = []
        with self._manager_mutex:
            for origin, entry in self._routepool.items():
                temp_worker_round_list.append(entry.rounds)

        return 0 if len(temp_worker_round_list) == 0 else min(temp_worker_round_list)

    def _other_worker_closer_to_prioq(self, prioqcoord, origin):
        logger.debug('Check distances from worker to prioQ coord')
        temp_distance: float = 0.0
        closer_worker = None
        if len(self._workers_registered) == 1:
            logger.debug('Route has only one worker - no distance check')
            return False

        current_worker_pos = self._routepool[origin].current_pos
        distance_worker = get_distance_of_two_points_in_meters(current_worker_pos.lat, current_worker_pos.lng,
                                                               prioqcoord.lat, prioqcoord.lng)

        logger.debug("Worker {} distance to PrioQ {}: {}", origin, prioqcoord, distance_worker)

        temp_distance = distance_worker

        for worker in self._routepool.keys():
            if worker == origin or self._routepool[worker].has_prio_event \
                    or self._routepool[origin].last_round_prio_event:
                continue
            worker_pos = self._routepool[worker].current_pos
            prio_distance = get_distance_of_two_points_in_meters(worker_pos.lat, worker_pos.lng,
                                                                 prioqcoord.lat, prioqcoord.lng)
            logger.debug("Worker {} distance to PrioQ {}: {}", worker, prioqcoord, prio_distance)
            if prio_distance < temp_distance:
                logger.debug("Worker {} closer then {} by {} meters",
                             worker,
                             origin,
                             int(distance_worker) - int(prio_distance))
                temp_distance = prio_distance
                closer_worker = worker

        if closer_worker is not None:
            with self._manager_mutex:
                self._routepool[closer_worker].has_prio_event = True
                self._routepool[closer_worker].prio_coords = prioqcoord
            logger.debug("Worker {} is closer to PrioQ event {}", closer_worker, prioqcoord)
            return True

        logger.debug("No Worker is closer to PrioQ event {} than {}", prioqcoord, origin)

        return False

    # to be called regularly to remove inactive workers that used to be registered
    def _check_routepools(self, timeout: int = 300):
        while not self._stop_update_thread.is_set():
            routepool_changed: bool = False
            logger.debug("Checking routepool for idle/dead workers")
            with self._manager_mutex:
                for origin in list(self._routepool):
                    entry: RoutePoolEntry = self._routepool[origin]
                    if time.time() - entry.last_access > timeout + entry.worker_sleeping:
                        logger.warning(
                            "Worker {} has not accessed a location in {} seconds, removing from routemanager",
                            origin, timeout)
                        self.unregister_worker(origin)

            i = 0
            while i < 60 and not self._stop_update_thread.is_set():
                if self._stop_update_thread.is_set():
                    logger.info("Stop checking routepools")
                    break
                i += 1
                time.sleep(1)

    def set_worker_sleeping(self, origin: str, sleep_duration: float):
        if sleep_duration > 0:
            with self._manager_mutex:
                if origin in self._routepool:
                    self._routepool[origin].worker_sleeping = sleep_duration

    def __worker_changed_update_routepools(self):
        less_coords: bool = False
        if not self._is_started:
            return True
        temp_coordplist: List[Location] = []
        if self.mode in ("iv_mitm", "idle"):
            logger.info('Not updating routepools in iv_mitm mode')
            return True
        with self._manager_mutex:
            logger.debug("Updating all routepools")
            if len(self._workers_registered) == 0:
                logger.info("No registered workers, aborting __worker_changed_update_routepools...")
                return False

            if len(self._workers_registered) > len(self._current_route_round_coords):
                less_coords = True
                new_subroute_length = len(self._current_route_round_coords)
            else:
                try:
                    new_subroute_length = math.floor(len(self._current_route_round_coords) /
                                                     len(self._workers_registered))
                    if new_subroute_length == 0:
                        return False
                except Exception as e:
                    logger.info('Something happens with the worker - breakup')
                    return False
            i: int = 0
            temp_total_round: collections.deque = collections.deque(self._current_route_round_coords)

            # we want to order the dict by the time's we added the workers to the areas
            # we first need to build a list of tuples with only origin, time_added
            logger.debug("Checking routepool: {}", self._routepool)
            reduced_routepools = [(origin, self._routepool[origin].time_added) for origin in self._routepool]
            sorted_routepools = sorted(reduced_routepools, key=itemgetter(1))

            logger.debug("Checking routepools in the following order: {}", sorted_routepools)
            compare = lambda x, y: collections.Counter(x) == collections.Counter(y)
            for origin, time_added in sorted_routepools:
                entry: RoutePoolEntry = self._routepool[origin]
                logger.debug("Checking subroute of {}", origin)
                # let's assume a worker has already been removed or added to the dict (keys)...

                new_subroute: List[Location] = []
                j: int = 0
                while len(temp_total_round) > 0 and (j <= new_subroute_length or i == len(self._routepool)):
                    j += 1
                    new_subroute.append(temp_total_round.popleft())

                i += 1
                if len(entry.subroute) == 0:
                    logger.debug("{}'s subroute is empty, assuming he has freshly registered and desperately needs a "
                                 "queue", origin)
                    # worker is freshly registering, pass him his fair share
                    entry.subroute = new_subroute
                    # let's clean the queue just to make sure
                    entry.queue.clear()
                elif len(new_subroute) == len(entry.subroute):
                    logger.debug("{}'s subroute is as long as the old one, we will assume it hasn't changed (for now)",
                                 origin)
                    # apparently nothing changed
                    if compare(new_subroute, entry.subroute):
                        logger.info("Apparently no changes in subroutes...")
                    else:
                        logger.critical("Subroute of {} has changed. Replacing entirely", origin)
                        # TODO: what now?
                        logger.debug('new_subroute: {}', new_subroute)
                        logger.debug('entry.subroute: {}', entry.subroute)
                        logger.debug('new_subroute == entry.subroute: {}', new_subroute == entry.subroute)
                        entry.subroute = new_subroute
                elif len(new_subroute) == 0:
                    logger.info("New subroute of {} is empty...", origin)
                    entry.subroute = new_subroute
                elif len(entry.subroute) > len(new_subroute) > 0:
                    logger.debug("{}'s subroute is longer than it should be now (maybe a worker has been "
                                 "added)", origin)
                    # we apparently have added at least a worker...
                    #   1) reduce the start of the current queue to start of new route
                    #   2) append the coords missing (check end of old routelength, add/remove from there on compared
                    #      to new)
                    old_queue: collections.deque = collections.deque(entry.queue)
                    while len(old_queue) > 0 and len(new_subroute) > 0 and old_queue.popleft() != new_subroute[0]:
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
                        logger.debug("Checking if the last element of the old queue is present in new subroute")
                        last_el_old_q: Location = old_queue[len(old_queue) - 1]
                        if last_el_old_q in new_subroute:
                            # we have the last element in the old subroute, we can actually append stuff with the
                            # diff to the new route
                            logger.debug("Last element of old queue is present in new subroute, appending the rest of "
                                         "the new subroute to the queue")
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
                    #   still in
                    #   the new route, remove the old rest of it (or just fetch the first coord of the next subroute and
                    #   remove the coords of that coord onward)
                    logger.debug("A worker has apparently been removed from the routepool")
                    last_el_old_route: Location = entry.subroute[len(entry.subroute) - 1]
                    old_queue_list: List[Location] = list(entry.queue)
                    old_queue: collections.deque = collections.deque(entry.queue)

                    last_el_new_route: Location = new_subroute[len(new_subroute) - 1]
                    # check last element of new subroute:
                    if last_el_new_route is not None and last_el_new_route in old_queue_list:
                        # if in current queue, remove from end of new subroute to end of old queue
                        logger.debug("Last element of new subroute is in old queue, removing everything after that "
                                     "element")
                        del old_queue_list[old_queue.index(last_el_new_route): len(old_queue_list) - 1]
                    elif last_el_old_route in new_subroute:
                        # append from end of queue (compared to new subroute) to end of new subroute
                        logger.debug("Last element of old queue in new subroute, appending everything afterwards")
                        missing_new_route_part: List[Location] = new_subroute.copy()
                        del missing_new_route_part[0: new_subroute.index(last_el_old_route)]
                        old_queue_list.extend(missing_new_route_part)

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

    def change_init_mapping(self, name_area: str):
        with open(args.mappings) as f:
            vars = json.load(f)

        for var in vars['areas']:
            if (var['name']) == name_area:
                var['init'] = bool(False)

        with open(args.mappings, 'w') as outfile:
            json.dump(vars, outfile, indent=4, sort_keys=True)

    def get_route_status(self, origin) -> Tuple[int, int]:
        if self._route and origin in self._routepool:
            entry: RoutePoolEntry = self._routepool[origin]
            return len(entry.subroute) - len(entry.queue), len(entry.subroute)
        return 1, 1

    def get_rounds(self, origin: str) -> int:
        return self.check_worker_rounds()

    def get_registered_workers(self) -> int:
        self._workers_registered_mutex.acquire()
        try:
            return len(self._workers_registered)
        finally:
            self._workers_registered_mutex.release()

    def get_position_type(self, origin: str) -> Optional[str]:
        return self._positiontyp.get(origin, None)

    def get_geofence_helper(self) -> Optional[GeofenceHelper]:
        return self.geofence_helper

    def get_init(self) -> bool:
        return self.init

    def get_mode(self):
        return self.mode

    def get_settings(self) -> Optional[dict]:
        return self.settings

    def get_current_route(self) -> List[Location]:
        return self._route

    def get_current_prioroute(self) -> List[Location]:
        return self._prio_queue

    def get_level_mode(self):
        return self._level

    def redo_stop(self, worker, lat, lon):
        logger.info('Worker {} redo a unprocessed Stop ({}, {})'.format(str(worker), str(lat), str(lon)))
        if worker in self._routepool:
            self._routepool[worker].has_prio_event = True
            self._routepool[worker].prio_coords = Location(lat, lon)
            return True
        return False

    def get_coords_from_workers(self):
        coordlist: List[Location] = []
        logger.info('Getting all coords from workers')
        for origin in self._routepool:
            [coordlist.append(i) for i in self._routepool[origin].queue]

        logger.debug('Open Coords from workers: {}'.format(str(coordlist)))
        return coordlist

