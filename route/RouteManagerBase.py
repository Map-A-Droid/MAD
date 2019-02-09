import collections
import heapq
import json
import logging
import os
import time
from abc import ABC, abstractmethod
from datetime import datetime
from threading import Event, Lock, Thread

import numpy as np
from geofence.geofenceHelper import GeofenceHelper
from route.routecalc.calculate_route import getJsonRoute
from route.routecalc.ClusteringHelper import ClusteringHelper
from utils.collections import Location

log = logging.getLogger(__name__)
Relation = collections.namedtuple(
    'Relation', ['other_event', 'distance', 'timedelta'])


class RouteManagerBase(ABC):
    def __init__(self, db_wrapper, coords, max_radius, max_coords_within_radius, path_to_include_geofence,
                 path_to_exclude_geofence, routefile, mode=None, init=False,
                 name="unknown", settings=None):
        self.db_wrapper = db_wrapper
        self.init = init
        self.name = name
        self._coords_unstructured = coords
        self.geofence_helper = GeofenceHelper(
            path_to_include_geofence, path_to_exclude_geofence)
        self._routefile = routefile
        self._max_radius = max_radius
        self._max_coords_within_radius = max_coords_within_radius
        self.settings = settings
        self.mode = mode

        self._last_round_prio = False
        self._manager_mutex = Lock()
        self._round_started_time = None
        if coords is not None:
            if init:
                fenced_coords = coords
            else:
                fenced_coords = self.geofence_helper.get_geofenced_coordinates(
                    coords)
            self._route = getJsonRoute(
                fenced_coords, max_radius, max_coords_within_radius, routefile)
        else:
            self._route = None
        self._current_index_of_route = 0
        self._init_mode_rounds = 0
        if settings is not None:
            self.delay_after_timestamp_prio = settings.get(
                "delay_after_prio_event", None)
            if self.delay_after_timestamp_prio == 0:
                self.delay_after_timestamp_prio = None
            self.starve_route = settings.get("starve_route", False)
        else:
            self.delay_after_timestamp_prio = None
            self.starve_route = False
        if self.delay_after_timestamp_prio is not None or mode == "iv_mitm":
            self._prio_queue = []
            if mode != "iv_mitm":
                self.clustering_helper = ClusteringHelper(self._max_radius,
                                                          self._max_coords_within_radius,
                                                          self._cluster_priority_queue_criteria())
            self._stop_update_thread = Event()
            self._update_prio_queue_thread = Thread(name="prio_queue_update_" + name,
                                                    target=self._update_priority_queue_loop)
            self._update_prio_queue_thread.daemon = True
            self._update_prio_queue_thread.start()
        else:
            self._prio_queue = None

    def __del__(self):
        if self.delay_after_timestamp_prio:
            self._stop_update_thread.set()
            self._update_prio_queue_thread.join()

    def clear_coords(self):
        self._manager_mutex.acquire()
        self._coords_unstructured = None
        self._manager_mutex.release()

    # list_coords is a numpy array of arrays!
    def add_coords_numpy(self, list_coords):
        fenced_coords = self.geofence_helper.get_geofenced_coordinates(
            list_coords)
        self._manager_mutex.acquire()
        if self._coords_unstructured is None:
            self._coords_unstructured = fenced_coords
        else:
            self._coords_unstructured = np.concatenate(
                (self._coords_unstructured, fenced_coords))
        self._manager_mutex.release()

    def add_coords_list(self, list_coords):
        to_be_appended = np.zeros(shape=(len(list_coords), 2))
        for i in range(len(list_coords)):
            to_be_appended[i][0] = list_coords[i][0]
            to_be_appended[i][1] = list_coords[i][1]
        self.add_coords_numpy(to_be_appended)

    @staticmethod
    def calculate_new_route(coords, max_radius, max_coords_within_radius, routefile, delete_old_route, num_procs=0):
        if delete_old_route and os.path.exists(routefile + ".calc"):
            log.debug("Deleting routefile...")
            os.remove(routefile + ".calc")
        new_route = getJsonRoute(coords, max_radius, max_coords_within_radius, num_processes=num_procs,
                                 routefile=routefile)
        return new_route

    def recalc_route(self, max_radius, max_coords_within_radius, num_procs=1, delete_old_route=False):
        current_coords = self._coords_unstructured
        routefile = self._routefile
        new_route = RouteManagerBase.calculate_new_route(current_coords, max_radius, max_coords_within_radius,
                                                         routefile, delete_old_route, num_procs)
        self._manager_mutex.acquire()
        self._route = new_route
        self._current_index_of_route = 0
        self._manager_mutex.release()

    def _update_priority_queue_loop(self):
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
            log.info("New priorityqueue: %s" % merged)

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

    @abstractmethod
    def _retrieve_latest_priority_queue(self):
        """
        Method that's supposed to return a plain list containing (timestamp, Location) of the next events of interest
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

    def get_next_location(self):
        log.debug("get_next_location of %s called" % str(self.name))
        next_lat, next_lng = 0, 0

        # first check if a location is available, if not, block until we have one...
        got_location = False
        while not got_location:
            log.debug("%s: Checking if a location is available..." %
                      str(self.name))
            self._manager_mutex.acquire()
            got_location = (self._prio_queue is not None and len(self._prio_queue) > 0
                            or (self._route is not None and len(self._route) > 0))
            self._manager_mutex.release()
            if not got_location:
                log.debug("%s: No location available yet" % str(self.name))
                time.sleep(0.5)
        log.debug(
            "%s: Location available, acquiring lock and trying to return location" % str(self.name))
        self._manager_mutex.acquire()
        # check priority queue for items of priority that are past our time...
        # if that is not the case, simply increase the index in route and return the location on route

        # determine whether we move to the next location or the prio queue top's item
        if (self.delay_after_timestamp_prio is not None and ((not self._last_round_prio or self.starve_route)
                                                             and self._prio_queue and len(self._prio_queue) > 0
                                                             and self._prio_queue[0][0] < time.time())):
            log.debug("%s: Priority event" % str(self.name))
            next_stop = heapq.heappop(self._prio_queue)[1]
            next_lat = next_stop.lat
            next_lng = next_stop.lng
            self._last_round_prio = True
            log.info("Round of route %s is moving to %s, %s for a priority event"
                     % (str(self.name), str(next_lat), str(next_lng)))
        else:
            log.debug("%s: Moving on with route" % str(self.name))
            if self._current_index_of_route == 0:
                if self._round_started_time is not None:
                    log.info("Round of route %s reached the first spot again. It took %s"
                             % (str(self.name), str(self._get_round_finished_string())))
                self._round_started_time = datetime.now()
                log.info("Round of route %s started at %s" %
                         (str(self.name), str(self._round_started_time)))

            # continue as usual
            log.info("Moving on with location %s" %
                     self._route[self._current_index_of_route])
            next_lat = self._route[self._current_index_of_route]['lat']
            next_lng = self._route[self._current_index_of_route]['lng']
            self._current_index_of_route += 1
            if self.init and self._current_index_of_route >= len(self._route):
                self._init_mode_rounds += 1
            if self.init and self._current_index_of_route >= len(self._route) and \
                    self._init_mode_rounds >= int(self.settings.get("init_mode_rounds", 1)):
                # we are done with init, let's calculate a new route
                log.warning("Init of %s done, it took %s, calculating new route..."
                            % (str(self.name), self._get_round_finished_string()))
                self._manager_mutex.release()
                self.clear_coords()
                coords = self._get_coords_post_init()
                log.debug("Setting %s coords to as new points in route of %s"
                          % (str(len(coords)), str(self.name)))
                self.add_coords_list(coords)
                log.debug("Route of %s is being calculated" % str(self.name))
                self.recalc_route(self._max_radius,
                                  self._max_coords_within_radius, 1, True)
                self.init = False
                self.change_init_mapping(self.name)
                return self.get_next_location()
            elif self._current_index_of_route >= len(self._route):
                self._current_index_of_route = 0
            self._last_round_prio = False
        log.info("%s done grabbing next coord, releasing lock and returning location: %s, %s"
                 % (str(self.name), str(next_lat), str(next_lng)))
        self._manager_mutex.release()
        return Location(next_lat, next_lng)

    def del_from_route(self):
        log.debug(
            "%s: Location available, acquiring lock and trying to return location" % str(self.name))
        self._manager_mutex.acquire()
        log.info('Removing coords from Route')
        self._route.pop(int(self._current_index_of_route)-1)
        self._current_index_of_route -= 1
        if len(self._route) == 0:
            log.info('No more coords are available... Sleeping.')
        self._manager_mutex.release()

    def change_init_mapping(self, name_area):
        with open('mappings.json') as f:
            vars = json.load(f)

        for var in vars['areas']:
            if (var['name']) == name_area:
                var['init'] = bool(False)

        with open('mappings.json', 'w') as outfile:
            json.dump(vars, outfile, indent=4, sort_keys=True)
