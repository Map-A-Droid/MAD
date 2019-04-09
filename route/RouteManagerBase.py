import collections
import heapq
import json
import os
import time
import numpy as np

from abc import ABC, abstractmethod
from threading import RLock, Event, Thread, Lock
from datetime import datetime
from queue import Queue
from loguru import logger
from geofence.geofenceHelper import GeofenceHelper
from route.routecalc.ClusteringHelper import ClusteringHelper
from route.routecalc.calculate_route import getJsonRoute
from utils.collections import Location


Relation = collections.namedtuple('Relation', ['other_event', 'distance', 'timedelta'])


class RouteManagerBase(ABC):
    def __init__(self, db_wrapper, coords, max_radius, max_coords_within_radius, path_to_include_geofence,
                 path_to_exclude_geofence, routefile, mode=None, init=False,
                 name="unknown", settings=None):
        self.db_wrapper = db_wrapper
        self.init = init
        self.name = name
        self._coords_unstructured = coords
        self.geofence_helper = GeofenceHelper(path_to_include_geofence, path_to_exclude_geofence)
        self._routefile = routefile
        self._max_radius = max_radius
        self._max_coords_within_radius = max_coords_within_radius
        self.settings = settings
        self.mode = mode
        self._is_started = False
        self._first_started = False
        self._route_queue = Queue()
        self._start_calc = False
        self._rounds = {}

        # we want to store the workers using the routemanager
        self._workers_registered = []
        self._workers_registered_mutex = Lock()

        self._last_round_prio = False
        self._manager_mutex = RLock()
        self._round_started_time = None
        if coords is not None:
            if init:
                fenced_coords = coords
            else:
                fenced_coords = self.geofence_helper.get_geofenced_coordinates(coords)
            self._route = getJsonRoute(fenced_coords, max_radius, max_coords_within_radius, routefile)
        else:
            self._route = None
        self._current_index_of_route = 0
        self._init_mode_rounds = 0

        if self.settings is not None:
            self.delay_after_timestamp_prio = self.settings.get("delay_after_prio_event", None)
            self.starve_route = self.settings.get("starve_route", False)
        else:
            self.delay_after_timestamp_prio = None
            self.starve_route = False

        # initialize priority queue variables
        self._prio_queue = None
        self._update_prio_queue_thread = None
        self._stop_update_thread = Event()

    def stop_routemanager(self):
        if self._update_prio_queue_thread is not None:
            self._stop_update_thread.set()
            self._update_prio_queue_thread.join()

    def _init_route_queue(self):
        self._manager_mutex.acquire()
        try:
            if len(self._route) > 0:
                self._route_queue.queue.clear()
                logger.debug("Creating queue for coords")
                for latlng in self._route:
                    self._route_queue.put((latlng['lat'], latlng['lng']))
                logger.debug("Finished creating queue")
        finally:
            self._manager_mutex.release()

    def clear_coords(self):
        self._manager_mutex.acquire()
        self._coords_unstructured = None
        self._manager_mutex.release()

    def register_worker(self, worker_name):
        self._workers_registered_mutex.acquire()
        try:
            if worker_name in self._workers_registered:
                logger.info("Worker {} already registered to routemanager {}", str(worker_name), str(self.name))
                return False
            else:
                logger.info("Worker {} registering to routemanager {}", str(worker_name), str(self.name))
                self._workers_registered.append(worker_name)
                self._rounds[worker_name] = 0

                return True
        finally:
            self._workers_registered_mutex.release()

    def unregister_worker(self, worker_name):
        self._workers_registered_mutex.acquire()
        try:
            if worker_name in self._workers_registered:
                logger.info("Worker {} unregistering from routemanager {}", str(worker_name), str(self.name))
                self._workers_registered.remove(worker_name)
                del self._rounds[worker_name]
            else:
                # TODO: handle differently?
                logger.info("Worker {} failed unregistering from routemanager {} since subscription was previously lifted", str(worker_name), str(self.name))
            if len(self._workers_registered) == 0 and self._is_started:
                logger.info("Routemanager {} does not have any subscribing workers anymore, calling stop", str(self.name))
                self._quit_route()
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
            self._update_prio_queue_thread.daemon = False
            self._update_prio_queue_thread.start()

    # list_coords is a numpy array of arrays!
    def add_coords_numpy(self, list_coords):
        fenced_coords = self.geofence_helper.get_geofenced_coordinates(list_coords)
        self._manager_mutex.acquire()
        if self._coords_unstructured is None:
            self._coords_unstructured = fenced_coords
        else:
            self._coords_unstructured = np.concatenate((self._coords_unstructured, fenced_coords))
        self._manager_mutex.release()

    def add_coords_list(self, list_coords):
        to_be_appended = np.zeros(shape=(len(list_coords), 2))
        for i in range(len(list_coords)):
            to_be_appended[i][0] = float(list_coords[i][0])
            to_be_appended[i][1] = float(list_coords[i][1])
        self.add_coords_numpy(to_be_appended)

    @staticmethod
    def calculate_new_route(coords, max_radius, max_coords_within_radius, routefile, delete_old_route, num_procs=0):
        if delete_old_route and os.path.exists(str(routefile) + ".calc"):
            logger.debug("Deleting routefile...")
            os.remove(str(routefile) + ".calc")
        new_route = getJsonRoute(coords, max_radius, max_coords_within_radius, num_processes=num_procs,
                                 routefile=routefile)
        return new_route

    def empty_routequeue(self):
        return self._route_queue.empty()

    def recalc_route(self, max_radius, max_coords_within_radius, num_procs=1, delete_old_route=False, nofile=False):
        current_coords = self._coords_unstructured
        if nofile:
            routefile = None
        else:
            routefile = self._routefile
        new_route = RouteManagerBase.calculate_new_route(current_coords, max_radius, max_coords_within_radius,
                                                         routefile, delete_old_route, num_procs)
        self._manager_mutex.acquire()
        self._route = new_route
        self._current_index_of_route = 0
        self._manager_mutex.release()

    def _update_priority_queue_loop(self):
        if self._priority_queue_update_interval() is None or self._priority_queue_update_interval() == 0:
            return
        while not self._stop_update_thread.is_set():
            # retrieve the latest hatches from DB
            # newQueue = self._db_wrapper.get_next_raid_hatches(self._delayAfterHatch, self._geofenceHelper)
            new_queue = self._retrieve_latest_priority_queue()
            self._merge_priority_queue(new_queue)
            time.sleep(self._priority_queue_update_interval())

    def _merge_priority_queue(self, new_queue):
        if new_queue is not None:
            self._manager_mutex.acquire()
            merged = set(new_queue + self._prio_queue)
            merged = list(merged)
            merged = self._filter_priority_queue_internal(merged)
            heapq.heapify(merged)
            self._prio_queue = merged
            self._manager_mutex.release()
            logger.info("New priority queue with {} entries", len(merged))
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
                            self.date_diff_in_seconds(round_finish_time, self._round_started_time)
                        )
                    )
        )
        return round_completed_in

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
    def _get_coords_after_finish_route(self):
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
            delete_seconds_passed = self.settings.get("remove_from_queue_backlog", 0)

        if delete_seconds_passed is not None:
            delete_before = time.time() - delete_seconds_passed
        else:
            delete_before = 0
        latest = [to_keep for to_keep in latest if not to_keep[0] < delete_before]
        # TODO: sort latest by modified flag of event
        # merged = self._merge_queue(latest, self._max_radius, 2, timedelta_seconds)
        merged = self.clustering_helper.get_clustered(latest)
        return merged

    def get_next_location(self):
        logger.debug("get_next_location of {} called", str(self.name))
        if not self._is_started:
            logger.info("Starting routemanager {} in get_next_location", str(self.name))
            self._start_routemanager()
        next_lat, next_lng = 0, 0

        if self._start_calc:
            logger.info("Another process already calculate the new route")
            return None

        # first check if a location is available, if not, block until we have one...
        got_location = False
        while not got_location and self._is_started and not self.init:
            logger.debug("{}: Checking if a location is available...", str(self.name))
            self._manager_mutex.acquire()
            got_location = not self._route_queue.empty() or (self._prio_queue is not None and len(self._prio_queue) > 0)
            self._manager_mutex.release()
            if not got_location:
                logger.debug("{}: No location available yet", str(self.name))
                if self._get_coords_after_finish_route() and not self.init:
                    # getting new coords or IV worker
                    time.sleep(1)
                else:
                    logger.info("Not getting new coords - leaving worker")
                    return None

        logger.debug("{}: Location available, acquiring lock and trying to return location", str(self.name))
        self._manager_mutex.acquire()
        # check priority queue for items of priority that are past our time...
        # if that is not the case, simply increase the index in route and return the location on route

        # determine whether we move to the next location or the prio queue top's item
        if (self.delay_after_timestamp_prio is not None and ((not self._last_round_prio or self.starve_route)
                                                             and self._prio_queue and len(self._prio_queue) > 0
                                                             and self._prio_queue[0][0] < time.time())):
            logger.debug("{}: Priority event", str(self.name))
            next_stop = heapq.heappop(self._prio_queue)[1]
            next_lat = next_stop.lat
            next_lng = next_stop.lng
            self._last_round_prio = True
            logger.info("Round of route {} is moving to {}, {} for a priority event", str(self.name), str(next_lat), str(next_lng))
        else:
            logger.debug("{}: Moving on with route", str(self.name))
            if len(self._route) == self._route_queue.qsize():
                if self._round_started_time is not None:
                    logger.info("Round of route {} reached the first spot again. It took {}", str(self.name), str(self._get_round_finished_string()))
                    self.add_route_to_origin()
                self._round_started_time = datetime.now()
                if len(self._route) == 0:
                    return None
                logger.info("Round of route {} started at {}", str(self.name), str(self._round_started_time))
            elif self._round_started_time is None:
                self._round_started_time = datetime.now()

            # continue as usual

            if self.init and (self._route_queue.empty()):
                self._init_mode_rounds += 1
            if self.init and (self._route_queue.empty()) and \
                    self._init_mode_rounds >= int(self.settings.get("init_mode_rounds", 1)):
                # we are done with init, let's calculate a new route
                logger.warning("Init of {} done, it took {}, calculating new route...", str(self.name), self._get_round_finished_string())
                if self._start_calc:
                    logger.info("Another process already calculate the new route")
                    self._manager_mutex.release()
                    return None
                self._start_calc = True
                self.clear_coords()
                coords = self._get_coords_post_init()
                logger.debug("Setting {} coords to as new points in route of {}", str(len(coords)), str(self.name))
                self.add_coords_list(coords)
                logger.debug("Route of {} is being calculated", str(self.name))
                self._recalc_route_workertype()
                self.init = False
                self.change_init_mapping(self.name)
                self._manager_mutex.release()
                self._start_calc = False
                logger.debug("Initroute of {} is finished - restart worker", str(self.name))
                return None
            elif (self._route_queue.qsize()) == 1:
                logger.info('Reaching last coord of route')
            elif self._route_queue.empty():
                # normal queue is empty - prioQ is filled. Try to generate a new Q
                logger.info("Normal routequeue is empty - try to fill up")
                if self._get_coords_after_finish_route():
                    # getting new coords or IV worker
                    self._manager_mutex.release()
                    return self.get_next_location()
                elif not self._get_coords_after_finish_route():
                    logger.info("Not getting new coords - leaving worker")
                    self._manager_mutex.release()
                    return None
                self._manager_mutex.release()

            # getting new coord
            next_coord = self._route_queue.get()
            next_lat = next_coord[0]
            next_lng = next_coord[1]
            self._route_queue.task_done()
            logger.info("{}: Moving on with location {} [{} coords left]", str(self.name), str(next_coord), str(self._route_queue.qsize()))

            self._last_round_prio = False
        logger.debug("{}: Done grabbing next coord, releasing lock and returning location: {}, {}", str(self.name), str(next_lat), str(next_lng))
        self._manager_mutex.release()
        if self._check_coords_before_returning(next_lat, next_lng):
            return Location(next_lat, next_lng)
        else:
            return self.get_next_location()

    def del_from_route(self):
        logger.debug("{}: Location available, acquiring lock and trying to return location", str(self.name))
        self._manager_mutex.acquire()
        logger.info('Removing coords from Route')
        self._route.pop(int(self._current_index_of_route)-1)
        self._current_index_of_route -= 1
        if len(self._route) == 0:
            logger.info('No more coords are available... Sleeping.')
        self._manager_mutex.release()

    def change_init_mapping(self, name_area):
        with open('configs/mappings.json') as f:
            vars = json.load(f)

        for var in vars['areas']:
            if (var['name']) == name_area:
                var['init'] = bool(False)

        with open('configs/mappings.json', 'w') as outfile:
            json.dump(vars, outfile, indent=4, sort_keys=True)

    def get_route_status(self):
        if self._route:
            return (len(self._route) - self._route_queue.qsize()), len(self._route)
        return 1, 1

    def get_rounds(self, origin):
        return self._rounds.get(origin, 999)

    def add_route_to_origin(self):
        for origin in self._rounds:
            self._rounds[origin] += 1

    def get_registered_workers(self):
        return len(self._workers_registered)
