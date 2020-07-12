import s2sphere

from mapadroid.utils.collections import Relation
from mapadroid.utils.geo import (
    get_distance_of_two_points_in_meters,
    get_middle_of_coord_list
)
from mapadroid.utils.s2Helper import S2Helper


class ClusteringHelper:
    def __init__(self, max_radius, max_count_per_circle, max_timedelta_seconds, useS2: bool = False,
                 S2level: int = 30):
        self.max_radius = max_radius
        self.max_count_per_circle = max_count_per_circle
        self.max_timedelta_seconds = max_timedelta_seconds
        self.useS2 = useS2
        self.S2level = S2level

    def _get_relations_in_range_within_time(self, queue, max_radius):
        relations = {}
        for event in queue:
            for other_event in queue:
                if event[1].lat == other_event[1].lat and event[1].lng == other_event[1].lng and \
                   event not in relations.keys():
                    relations[event] = []
                distance = get_distance_of_two_points_in_meters(event[1].lat, event[1].lng,
                                                                other_event[1].lat, other_event[1].lng)
                # we will always build relations from the event at hand subtracted by the event inspected
                timedelta = event[0] - other_event[0]
                if 0 <= distance <= max_radius * 2 and 0 <= timedelta <= self.max_timedelta_seconds:
                    if event not in relations.keys():
                        relations[event] = []
                    # avoid duplicates
                    already_present = False
                    for relation in relations[event]:
                        if relation[0][1].lat == other_event[1].lat and \
                           relation[0][1].lng == other_event[1].lng:
                            already_present = True
                    if not already_present:
                        relations[event].append(
                            Relation(other_event, distance, timedelta))
        return relations

    def _get_most_west_amongst_relations(self, relations):
        selected = list(relations.keys())[0]
        for event in relations.keys():
            if event[1].lng < selected[1].lng:
                selected = event
            elif event[1].lng == selected[1].lng and event[1].lat > selected[1].lat:
                selected = event
        return selected

    def _get_farthest_in_relation(self, to_be_inspected):
        # retrieve the relation farthest within the given timedelta, do not bother about maximizing the timedelta
        # if a coord is not within the given timedeltas, it will simply remain in the original set anyway ;)
        # ignore any relations of previously merged origins for now
        distance = -1
        farthest = None
        for relation in to_be_inspected:
            if (len(relation.other_event) == 4 and not relation.other_event[3] or len(relation) < 4) and \
               relation.timedelta <= self.max_timedelta_seconds and relation.distance > distance:
                distance = relation.distance
                farthest = relation
        return farthest.other_event, distance

    def _get_count_and_coords_in_circle_within_timedelta(self, middle, relations, earliest_timestamp,
                                                         latest_timestamp, max_radius):
        inside_circle = []
        highest_timedelta = 0
        if self.useS2:
            region = s2sphere.CellUnion(
                S2Helper.get_S2cells_from_circle(middle.lat, middle.lng, self.max_radius, self.S2level))

        for event_relations in relations:
            # exclude previously clustered events...
            if len(event_relations) == 4 and event_relations[3]:
                inside_circle.append(event_relations)
                continue
            distance = get_distance_of_two_points_in_meters(middle.lat, middle.lng,
                                                            event_relations[1].lat,
                                                            event_relations[1].lng)
            event_in_range = 0 <= distance <= max_radius
            if self.useS2:
                event_in_range = region.contains(s2sphere.LatLng.from_degrees(event_relations[1].lat,
                                                                              event_relations[1].lng).to_point())
            # timedelta of event being inspected to the earliest timestamp
            timedelta_end = latest_timestamp - event_relations[0]
            timedelta_start = event_relations[0] - earliest_timestamp
            if timedelta_end < 0 and event_in_range:
                # we found an event starting past the current latest timestamp, let's update the latest_timestamp
                latest_timestamp_temp = latest_timestamp + abs(timedelta_end)
                if latest_timestamp_temp - earliest_timestamp <= self.max_timedelta_seconds:
                    latest_timestamp = latest_timestamp_temp
                    highest_timedelta = highest_timedelta + abs(timedelta_end)
                    inside_circle.append(event_relations)
            elif timedelta_start < 0 and event_in_range:
                # we found an event starting before earliest_timestamp, let's check that...
                earliest_timestamp_temp = earliest_timestamp - abs(timedelta_start)
                if latest_timestamp - earliest_timestamp_temp <= self.max_timedelta_seconds:
                    earliest_timestamp = earliest_timestamp_temp
                    highest_timedelta = highest_timedelta + abs(timedelta_start)
                    inside_circle.append(event_relations)
            elif timedelta_end >= 0 and timedelta_start >= 0 and event_in_range:
                # we found an event within our current timedelta and proximity, just append it to the list
                inside_circle.append(event_relations)

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

    def _get_circle(self, event, to_be_inspected, relations, max_radius):
        if len(to_be_inspected) == 0:
            return event, [event]
        elif len(to_be_inspected) == 1:
            # TODO: do relations hold themselves or is there a return missing here?
            return event, [event]
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
            farthest_away, distance_to_farthest = self._get_farthest_in_relation(
                to_be_inspected)
            all_events_within_range_and_time = [event, farthest_away]
            earliest_timestamp = self._get_earliest_timestamp_in_queue(
                all_events_within_range_and_time)
            latest_timestamp = self._get_latest_timestamp_in_queue(
                all_events_within_range_and_time)
            middle = get_middle_of_coord_list(
                [event[1], farthest_away[1]]
            )
            middle_event = (
                latest_timestamp, middle, latest_timestamp - earliest_timestamp, True
            )
        count_inside, events_in_circle, highest_timedelta, latest_timestamp = \
            self._get_count_and_coords_in_circle_within_timedelta(middle, relations,
                                                                  earliest_timestamp, latest_timestamp,
                                                                  max_radius)
        middle_event = (latest_timestamp, middle_event[1],
                        highest_timedelta, middle_event[3])
        if count_inside <= self.max_count_per_circle and count_inside == len(to_be_inspected):
            return middle_event, events_in_circle
        elif count_inside > self.max_count_per_circle:
            to_be_inspected = [
                to_keep for to_keep in to_be_inspected if not to_keep.other_event == farthest_away]
            return self._get_circle(event, to_be_inspected, relations, distance_to_farthest)
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

    def _sum_up_relations(self, relations):
        final_set = []

        while len(relations) > 0:
            next = self._get_most_west_amongst_relations(relations)
            middle_event, events_to_be_removed = self._get_circle(
                next, relations[next], relations, self.max_radius)
            final_set.append(middle_event)
            relations = self._remove_coords_from_relations(
                relations, events_to_be_removed)
        return final_set

    def get_clustered(self, queue):
        relations = self._get_relations_in_range_within_time(
            queue, max_radius=self.max_radius)
        summed_up = self._sum_up_relations(relations)
        return summed_up
