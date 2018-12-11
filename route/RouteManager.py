import collections
import heapq
import logging
import os
import time
from datetime import datetime
from threading import Thread, Event, Lock

import numpy as np

from geofence.geofenceHelper import GeofenceHelper
from .routecalc.calculate_route import getJsonRoute

Location = collections.namedtuple('Location', ['lat', 'lng'])

log = logging.getLogger(__name__)


# each "device" is handed a RouteManager. If there are no mappings, the calling function needs to pass a single
# RouteManager to all the devices...
class RouteManager:
    def __init__(self, db_wrapper, coords, maxRadius, maxCoordsWithinRadius, pathToIncludeGeofence,
                 pathToExcludeGeofence,
                 routefile, coords_spawns_known=False, delayAfterHatch=None, init=False, mode=None, settings=None,
                 name="unknown"):
        # TODO: handle mode=None...
        # first filter the coords with the geofence given
        self.init = init
        self.mode = mode
        self.name = name
        self.settings = settings
        self.coords_spawns_known = coords_spawns_known
        self.__coords_unstructured = coords
        self.__geofenceHelper = GeofenceHelper(pathToIncludeGeofence, pathToExcludeGeofence)
        self.__db_wrapper = db_wrapper
        self.__managerMutex = Lock()
        self.__lastRoundEggHatch = False  # boolean to prevent starvation in a simple way...
        self.__routefile = routefile
        self.__max_radius = maxRadius
        self.__max_coords_within_radius = maxCoordsWithinRadius

        self.__round_started_time = None

        if coords is not None:
            if init:
                fencedCoords = coords
            else:
                fencedCoords = self.__geofenceHelper.get_geofenced_coordinates(coords)
            self.__route = getJsonRoute(fencedCoords, maxRadius, maxCoordsWithinRadius, routefile)
        else:
            self.__route = None
        self.__currentIndexOfRoute = 0
        # heapq of hatched eggs
        self.__delayAfterHatch = delayAfterHatch
        if self.__delayAfterHatch is not None:
            self.__raidQueue = []
            self.__stopUpdateThread = Event()
            self.__updateRaidQueueThread = Thread(name='raidQUpdate', target=self.__updatePriorityQueueLoop)
            self.__updateRaidQueueThread.daemon = False
            self.__updateRaidQueueThread.start()
        else:
            self.__raidQueue = None

    def __del__(self):
        if self.__delayAfterHatch:
            self.__stopUpdateThread.set()
            self.__updateRaidQueueThread.join()

    def clear_coords(self):
        self.__managerMutex.acquire()
        self.__coords_unstructured = None
        self.__managerMutex.release()

    # list_coords is a numpy array of arrays!
    def add_coords_numpy(self, list_coords):
        fenced_coords = self.__geofenceHelper.get_geofenced_coordinates(list_coords)
        self.__managerMutex.acquire()
        if self.__coords_unstructured is None:
            self.__coords_unstructured = fenced_coords
        else:
            self.__coords_unstructured = np.concatenate((self.__coords_unstructured, fenced_coords))
        self.__managerMutex.release()

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
        current_coords = self.__coords_unstructured
        routefile = self.__routefile
        new_route = RouteManager.calculate_new_route(current_coords, max_radius, max_coords_within_radius,
                                                     routefile, delete_old_route, num_procs)
        self.__managerMutex.acquire()
        self.__route = new_route
        self.__currentIndexOfRoute = 0
        self.__managerMutex.release()

    def __updatePriorityQueueLoop(self):
        while not self.__stopUpdateThread.is_set():
            # retrieve the latest hatches from DB
            newQueue = self.__db_wrapper.get_next_raid_hatches(self.__delayAfterHatch, self.__geofenceHelper)
            self.__mergeRaidQueue(newQueue)
            time.sleep(300)

    def __mergeRaidQueue(self, newQueue):
        self.__managerMutex.acquire()
        merged = list(set(newQueue + self.__raidQueue))
        heapq.heapify(merged)
        self.__raidQueue = merged
        self.__managerMutex.release()
        log.info("New raidqueue: %s" % merged)

    def getNextLocation(self):
        # nextLocation = Location(None, None)
        nextLat = 0
        nextLng = 0

        # first check if a location is available, if not, block until we have one... TODO
        got_location = False
        while not got_location:
            self.__managerMutex.acquire()
            got_location = self.__raidQueue is not None and len(self.__raidQueue) > 0 or len(self.__route) > 0
            self.__managerMutex.release()
            if not got_location:
                time.sleep(0.5)

        self.__managerMutex.acquire()
        # check raid queue for hatches, if none have passed, simply increase index and return the location in the route
        # at index
        # determine whether we move to the next gym or to the top of our priority queue
        if self.__delayAfterHatch is not None and (not self.__lastRoundEggHatch and len(self.__raidQueue) > 0
                                                   and self.__raidQueue[0][0] < time.time()):
            nextStop = heapq.heappop(self.__raidQueue)[1]  # gets the location tuple
            nextLat = nextStop.latitude
            nextLng = nextStop.longitude
            self.__lastRoundEggHatch = True
        else:
            if self.__currentIndexOfRoute == 0:
                if self.__round_started_time is not None:
                    log.info("Round of route %s reached the first spot again. It took: %s"
                             % (str(self.name), self.get_round_finished_string()))
                self.__round_started_time = datetime.now()
                log.info("Round of route %s started at %s" % (str(self.name), str(self.__round_started_time)))
            # continue as usual
            log.info('main: Moving on with gym at %s' % self.__route[self.__currentIndexOfRoute])
            nextLat = self.__route[self.__currentIndexOfRoute]['lat']
            nextLng = self.__route[self.__currentIndexOfRoute]['lng']
            self.__currentIndexOfRoute += 1
            if self.init and self.__currentIndexOfRoute >= len(self.__route):
                # we are done with init, let's calculate a new route

                log.warning("Init of %s done, it took %s, calculating new route..."
                            % (str(self.name), self.get_round_finished_string()))
                self.__managerMutex.release()
                self.clear_coords()
                if self.mode == "raids_ocr" or self.mode == "raids_mitm":
                    coords = self.__db_wrapper.gyms_from_db(self.__geofenceHelper)
                elif self.mode == "mon_mitm":
                    if self.coords_spawns_known:
                        log.info("Reading known Spawnpoints from DB")
                        coords = self.__db_wrapper.get_detected_spawns(self.__geofenceHelper)
                    else:
                        log.info("Reading unknown Spawnpoints from DB")
                        coords = self.__db_wrapper.get_undetected_spawns(self.__geofenceHelper)
                else:
                    log.fatal("Mode not implemented yet: %s" % str(self.mode))
                    exit(1)
                log.debug("Adding %s coords to list" % str(len(coords)))
                self.add_coords_list(coords)
                log.debug("Runnig calculation")
                self.recalc_route(self.__max_radius, self.__max_coords_within_radius, 1, True)
                self.init = False
                log.debug("Calling ourself to get coord...")
                return self.getNextLocation()
            elif self.__currentIndexOfRoute >= len(self.__route):
                self.__currentIndexOfRoute = 0
            self.__lastRoundEggHatch = False
        self.__managerMutex.release()
        return Location(nextLat, nextLng)

    def date_diff_in_seconds(self, dt2, dt1):
        timedelta = dt2 - dt1
        return timedelta.days * 24 * 3600 + timedelta.seconds

    def dhms_from_seconds(self, seconds):
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        # days, hours = divmod(hours, 24)
        return hours, minutes, seconds

    def get_round_finished_string(self):
        round_finish_time = datetime.now()
        round_completed_in = (
                "%d hours, %d minutes, %d seconds" % (
            self.dhms_from_seconds(
                self.date_diff_in_seconds(round_finish_time, self.__round_started_time)
            )
        )
        )
        return round_completed_in
