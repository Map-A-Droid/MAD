import collections
import heapq
import logging
import os
import time
import numpy as np
from abc import ABC, abstractmethod
from threading import Lock, Event, Thread
from datetime import datetime

from geofence.geofenceHelper import GeofenceHelper
from route.routecalc.calculate_route import getJsonRoute
from utils.collections import Location
from utils.geo import get_distance_of_two_points_in_meters, get_middle_of_coord_list

log = logging.getLogger(__name__)

Relation = collections.namedtuple('Relation', ['other_event', 'distance', 'timedelta'])


class RouteManagerBase(ABC):
    def __init__(self, db_wrapper, coords, max_radius, max_coords_within_radius, path_to_include_geofence,
                 path_to_exclude_geofence, routefile, init=False,
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

        self._last_round_prio = False
        self._manager_mutex = Lock()
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
        if settings is not None:
            self.delay_after_timestamp_prio = settings.get("delay_after_prio_event", None)
            self.starve_route = settings.get("starve_route", False)
        else:
            self.delay_after_timestamp_prio = None
            self.starve_route = False
        if self.delay_after_timestamp_prio is not None:
            self._prio_queue = []
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
            time.sleep(300)

    def _merge_priority_queue(self, new_queue):
        self._manager_mutex.acquire()
        merged = list(set(new_queue + self._prio_queue))
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

    def _get_relations_in_range_within_time(self, queue, max_radius, max_timedelta):
        relations = {}
        for event in queue:
            for other_event in queue:
                if (event[1].lat == other_event[1].lat and event[1].lng == other_event[1].lng
                        and event not in relations.keys()):
                    relations[event] = []
                distance = get_distance_of_two_points_in_meters(event[1].lat, event[1].lng,
                                                                other_event[1].lat, other_event[1].lng)
                # we will always build relations from the event at hand subtracted by the event inspected
                timedelta = event[0] - other_event[0]
                if 0 <= distance <= max_radius * 2 and 0 <= timedelta <= max_timedelta:
                    if event not in relations.keys():
                        relations[event] = []
                    # avoid duplicates
                    already_present = False
                    for relation in relations[event]:
                        if (relation[0][1].lat == other_event[1].lat
                                and relation[0][1].lng == other_event[1].lng):
                            already_present = True
                    if not already_present:
                        relations[event].append(Relation(other_event, distance, timedelta))
        return relations

    def _get_most_west_amongst_relations(self, relations):
        selected = list(relations.keys())[0]
        for event in relations.keys():
            if event[1].lng < selected[1].lng:
                selected = event
            elif event[1].lng == selected[1].lng and event[1].lat > selected[1].lat:
                selected = event
        return selected

    def _get_farthest_in_relation(self, to_be_inspected, max_timedelta):
        # retrieve the relation farthest within the given timedelta, do not bother about maximizing the timedelta
        # if a coord is not within the given timedeltas, it will simply remain in the original set anyway ;)
        # ignore any relations of previously merged origins for now
        distance = -1
        farthest = None
        for relation in to_be_inspected:
            if (len(relation.other_event) == 4 and not relation.other_event[3] or len(relation) < 4) and relation.timedelta <= max_timedelta and relation.distance > distance:
                distance = relation.distance
                farthest = relation
        return farthest.other_event, distance

    def _get_count_and_coords_in_circle_within_timedelta(self, middle, relations, earliest_timestamp,
                                                         latest_timestamp, max_radius,
                                                         max_timedelta):
        inside_circle = []
        highest_timedelta = 0
        for event_relations in relations:
            # exclude previously clustered events...
            if len(event_relations) == 4 and event_relations[3]:
                inside_circle.append(event_relations)
                continue
            distance = get_distance_of_two_points_in_meters(middle.lat, middle.lng,
                                                            event_relations[1].lat,
                                                            event_relations[1].lng)
            # timedelta of event being inspected to the earliest timestamp
            timedelta_end = latest_timestamp - event_relations[0]
            timedelta_start = event_relations[0] - earliest_timestamp
            if timedelta_end < 0 and 0 <= distance <= max_radius:
                # we found an event starting past the current latest timestamp, let's update the latest_timestamp
                latest_timestamp_temp = latest_timestamp + abs(timedelta_end)
                if latest_timestamp_temp - earliest_timestamp <= max_timedelta:
                    latest_timestamp = latest_timestamp_temp
                    highest_timedelta = highest_timedelta + abs(timedelta_end)
                    inside_circle.append(event_relations)
            elif timedelta_start < 0 and 0 <= distance <= max_radius:
                # we found an event starting before earliest_timestamp, let's check that...
                earliest_timestamp_temp = earliest_timestamp - abs(timedelta_start)
                if latest_timestamp - earliest_timestamp_temp <= max_timedelta:
                    earliest_timestamp = earliest_timestamp_temp
                    highest_timedelta = highest_timedelta + abs(timedelta_start)
                    inside_circle.append(event_relations)
            elif timedelta_end >= 0 and timedelta_start >= 0 and 0 <= distance <= max_radius:
                # we found an event within our current timedelta and proximity, just append it to the list
                inside_circle.append(event_relations)
            #
            # elif 0 <= timedelta_end <= max_timedelta and 0 <= distance <= max_radius:
            #     earliest_timestamp_temp = earliest_timestamp
            #     if highest_timedelta < timedelta_end:
            #         highest_timedelta = timedelta_end
            #     inside_circle.append(event_relations)
        return len(inside_circle), inside_circle, highest_timedelta, latest_timestamp

    def _get_earliest_timestamp_in_queue(self, queue):
        earliest = queue[0][0]
        for item in queue:
            if earliest > item[0]:
                earliest = item[0]
        return earliest

    def _get_latest_timestamp_in_queue(self, queue):
        latest = queue[0][0]
        for item in queue:
            if latest < item[0]:
                latest = item[0]
        return latest

    def _get_circle(self, event, to_be_inspected, relations, max_radius, max_count_per_circle, max_timedelta):
        if len(to_be_inspected) == 0:
            return event, []
        elif len(to_be_inspected) == 1:
            # TODO: merge event with the relation? this looks fishy, pretty sure we would need to remove the
            # other coord in the to_be_inspected as well?
            # TODO: do we not need to return the relation here?
            return event, [event]
            # if event[3]:
            #     # the event has previously been merged with others, if the timedelta meets the criteria,
            #     # return the event
            #     # event[2] is the timedelta of the earliest merged to the timestamp of the event (latest in time)
            #     # if relations only item's timestamp is greater than event, we will have a total timedelta to compare
            #     # else we will likely have an item that can safely be merged/deleted
            #     timedelta_event_to_single_relation = event[2] + (to_be_inspected[0][0] - event[0])
            #     if timedelta_event_to_single_relation <= event[2]:
            #         # we can safely remove the relation
            #         return event, [event]
        # TODO: check if event[3] = true, if so, reduce max_timedelta by the timedelta given in event[2] and do not
        # use the get_farthest... since we have previously moved the middle, we need to check for matching events in
        # such cases and build new circle events in time
        if len(event) == 4 and event[3]:
            # this is a previously clustered event, we will simply check for other events that have not been clustered
            # to include those in our current circle
            # all we need to do is update timestamps to keep track as to whether we are still inside the max_timedelta
            # constraint
            middle_event = event
            middle = event[1]
            earliest_timestamp = event[0] - event[2]
            latest_timestamp = event[0]
            farthest_away = event
            distance_to_farthest = max_radius
        else:
            farthest_away, distance_to_farthest = self._get_farthest_in_relation(to_be_inspected, max_timedelta)
            all_events_within_range_and_time = [event, farthest_away]
            earliest_timestamp = self._get_earliest_timestamp_in_queue(all_events_within_range_and_time)
            latest_timestamp = self._get_latest_timestamp_in_queue(all_events_within_range_and_time)
            middle = get_middle_of_coord_list(
                [event[1], farthest_away[1]]
            )
            middle_event = (
                latest_timestamp, middle, latest_timestamp - earliest_timestamp, True
            )
        count_inside, events_in_circle, highest_timedelta, latest_timestamp = \
            self._get_count_and_coords_in_circle_within_timedelta(
                middle, relations, earliest_timestamp, latest_timestamp, max_radius, max_timedelta)
        middle_event = (latest_timestamp, middle_event[1],
                        highest_timedelta, middle_event[3])
        if count_inside <= max_count_per_circle and count_inside == len(to_be_inspected):
            return middle_event, events_in_circle
        elif count_inside > max_count_per_circle:
            to_be_inspected = [to_keep for to_keep in to_be_inspected if not to_keep.other_event == farthest_away]
            return self._get_circle(event, to_be_inspected, relations, distance_to_farthest, max_count_per_circle,
                                    max_timedelta)
        else:
            return middle_event, events_in_circle

    def _remove_coords_from_relations(self, relations, events_to_be_removed):
        for source_event, relations_to_source in list(relations.items()):
            # iterate relations, remove anything matching events_to_be_removed
            for event in events_to_be_removed:
                if event == source_event:
                    relations.pop(source_event)
                    break
                # iterate through the entire distance relations as well...
                for relation in relations_to_source:
                    if relation.other_event[1] == event[1]:
                        relations[source_event].remove(relation)
        return relations

    def _sum_up_relations(self, relations, max_radius, max_count_per_circle, max_timedelta):
        final_set = []

        while len(relations) > 0:
            next = self._get_most_west_amongst_relations(relations)
            middle_event, events_to_be_removed = self._get_circle(next, relations[next], relations, max_radius,
                                                                 max_count_per_circle, max_timedelta)
            final_set.append(middle_event)
            relations = self._remove_coords_from_relations(relations, events_to_be_removed)
        return final_set

    def _merge_queue(self, queue, max_radius, max_count_per_circle, max_timedelta_seconds):
        relations = self._get_relations_in_range_within_time(queue, max_radius, max_timedelta_seconds)
        summed_up = self._sum_up_relations(relations, max_radius, max_count_per_circle, max_timedelta_seconds)
        return summed_up

    def _filter_priority_queue_internal(self, latest):
        """
        Filter through the internal priority queue and cluster events within the timedelta and distance returned by
        _cluster_priority_queue_criteria
        :return:
        """
        timedelta_seconds = self._cluster_priority_queue_criteria()
        merged = self._merge_queue(latest, self._max_radius, 2, timedelta_seconds)
        # TODO: filter out events that occured too far in the past
        return merged

    def get_next_location(self):
        next_lat, next_lng = 0, 0

        # first check if a location is available, if not, block until we have one...
        got_location = False
        while not got_location:
            self._manager_mutex.acquire()
            got_location = self._prio_queue is not None and len(self._prio_queue) > 0 or len(self._route) > 0
            self._manager_mutex.release()
            if not got_location:
                time.sleep(0.5)

        self._manager_mutex.acquire()
        # check priority queue for items of priority that are past our time...
        # if that is not the case, simply increase the index in route and return the location on route

        # determine whether we move to the next location or the prio queue top's item
        if (self.delay_after_timestamp_prio is not None and ((not self._last_round_prio or self.starve_route)
                                                             and len(self._prio_queue) > 0
                                                             and self._prio_queue[0][0] < time.time())):
            next_stop = heapq.heappop(self._prio_queue)[1]
            next_lat = next_stop.lat
            next_lng = next_stop.lng
            self._last_round_prio = True
            log.info("Round of route %s is moving to %s, %s for a priority event"
                     % (str(self.name), str(next_lat), str(next_lng)))
        else:
            if self._current_index_of_route == 0:
                if self._round_started_time is not None:
                    log.info("Round of route %s reached the first spot again. It took %s"
                             % (str(self.name), str(self._get_round_finished_string())))
                self._round_started_time = datetime.now()
                log.info("Round of route %s started at %s" % (str(self.name), str(self._round_started_time)))

            # continue as usual
            log.info("Moving on with location %s" % self._route[self._current_index_of_route])
            next_lat = self._route[self._current_index_of_route]['lat']
            next_lng = self._route[self._current_index_of_route]['lng']
            self._current_index_of_route += 1
            if self.init and self._current_index_of_route >= len(self._route):
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
                self.recalc_route(self._max_radius, self._max_coords_within_radius, 1, True)
                self.init = False
                return self.get_next_location()
            elif self._current_index_of_route >= len(self._route):
                self._current_index_of_route = 0
            self._last_round_prio = False
        log.info("%s done grabbing next coord, releasing lock and returning location: %s, %s"
                 % (str(self.name), str(next_lat), str(next_lng)))
        self._manager_mutex.release()
        return Location(next_lat, next_lng)
