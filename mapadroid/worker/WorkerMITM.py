import math
import time
from datetime import datetime
from typing import Union, Tuple, Optional

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.mitm_receiver.MitmMapper import MitmMapper
from mapadroid.ocr.pogoWindows import PogoWindows
from mapadroid.utils import MappingManager
from mapadroid.utils.collections import Location
from mapadroid.utils.geo import (
    get_distance_of_two_points_in_meters,
    get_lat_lng_offsets_by_distance
)
from mapadroid.utils.madGlobals import InternalStopWorkerException
from mapadroid.websocket.AbstractCommunicator import AbstractCommunicator
from mapadroid.worker.MITMBase import MITMBase, LatestReceivedType
from mapadroid.utils.logging import get_logger, LoggerEnums


logger = get_logger(LoggerEnums.worker)


class WorkerMITM(MITMBase):
    def __init__(self, args, dev_id, origin, last_known_state, communicator: AbstractCommunicator,
                 mapping_manager: MappingManager, area_id: int, routemanager_name: str, mitm_mapper: MitmMapper,
                 db_wrapper: DbWrapper, pogo_window_manager: PogoWindows, walker, event):
        MITMBase.__init__(self, args, dev_id, origin, last_known_state, communicator,
                          mapping_manager=mapping_manager, area_id=area_id,
                          routemanager_name=routemanager_name,
                          db_wrapper=db_wrapper,
                          mitm_mapper=mitm_mapper, pogo_window_manager=pogo_window_manager, walker=walker, event=event)
        # TODO: own InjectionSettings class
        self.__update_injection_settings()

    def _health_check(self):
        self.logger.debug4("_health_check: called")
        pass

    def _cleanup(self):
        # no additional cleanup in MITM yet
        pass

    def _post_move_location_routine(self, timestamp):
        # TODO: pass the appropiate proto number if IV?
        if self._wait_for_data(timestamp) != LatestReceivedType.GMO:
            self.logger.warning("Worker failed to retrieve proper data at {}, {}. Worker will continue with "
                                "the next location", self.current_location.lat, self.current_location.lng)

    def _move_to_location(self):
        if not self._mapping_manager.routemanager_present(self._routemanager_name) \
                or self._stop_worker_event.is_set():
            raise InternalStopWorkerException
        routemanager_settings = self._mapping_manager.routemanager_get_settings(self._routemanager_name)
        # get the distance from our current position (last) to the next gym (cur)
        distance = get_distance_of_two_points_in_meters(float(self.last_location.lat),
                                                        float(self.last_location.lng),
                                                        float(self.current_location.lat),
                                                        float(self.current_location.lng))
        self.logger.debug('Moving {} meters to the next position', round(distance, 2))
        if not self._mapping_manager.routemanager_get_init(self._routemanager_name):
            speed = routemanager_settings.get("speed", 0)
            max_distance = routemanager_settings.get("max_distance", None)
        else:
            speed = int(25)
            max_distance = int(200)

        if (speed == 0 or
                (max_distance and 0 < max_distance < distance) or
                (self.last_location.lat == 0.0 and self.last_location.lng == 0.0)):
            self.logger.debug("main: Teleporting...")
            self._transporttype = 0
            self._communicator.set_location(
                Location(self.current_location.lat, self.current_location.lng), 0)
            # the time we will take as a starting point to wait for data...
            cur_time = math.floor(time.time())

            delay_used = self.get_devicesettings_value('post_teleport_delay', 0)
            # Test for cooldown / teleported distance TODO: check this block...
            if self.get_devicesettings_value('cool_down_sleep', False):
                if distance > 10000:
                    delay_used = 15
                elif distance > 5000:
                    delay_used = 10
                elif distance > 2500:
                    delay_used = 8
                self.logger.debug("Need more sleep after Teleport: {} seconds!", delay_used)
            walk_distance_post_teleport = self.get_devicesettings_value('walk_after_teleport_distance', 0)
            if 0 < walk_distance_post_teleport < distance:
                # TODO: actually use to_walk for distance
                lat_offset, lng_offset = get_lat_lng_offsets_by_distance(
                    walk_distance_post_teleport)

                to_walk = get_distance_of_two_points_in_meters(float(self.current_location.lat),
                                                               float(
                                                                   self.current_location.lng),
                                                               float(
                                                                   self.current_location.lat) + lat_offset,
                                                               float(self.current_location.lng) + lng_offset)
                self.logger.info("Walking roughly: {:.2f}m", to_walk)
                time.sleep(0.3)
                self._communicator.walk_from_to(self.current_location,
                                                Location(self.current_location.lat + lat_offset,
                                                         self.current_location.lng + lng_offset),
                                                11)
                self.logger.debug("Walking back")
                time.sleep(0.3)
                self._communicator.walk_from_to(Location(self.current_location.lat + lat_offset,
                                                self.current_location.lng + lng_offset),
                                                self.current_location,
                                                11)
                self.logger.debug("Done walking")
                time.sleep(1)
        else:
            self.logger.info("main: Walking...")
            self._transporttype = 1
            self._communicator.walk_from_to(self.last_location, self.current_location, speed)
            # the time we will take as a starting point to wait for data...
            cur_time = math.floor(time.time())
            self.logger.debug2("Done walking, fetching time to sleep")
            delay_used = self.get_devicesettings_value('post_walk_delay', 0)
        self.logger.debug2("Sleeping for {}s", delay_used)
        time.sleep(float(delay_used))
        self.set_devicesettings_value("last_location", self.current_location)
        self.last_location = self.current_location
        self._waittime_without_delays = time.time()
        return cur_time, True

    def _pre_location_update(self):
        self.__update_injection_settings()

    def _pre_work_loop(self):
        self.logger.info("MITM worker starting")
        if not self._wait_for_injection() or self._stop_worker_event.is_set():
            raise InternalStopWorkerException

        reached_main_menu = self._check_pogo_main_screen(10, True)
        if not reached_main_menu:
            if not self._restart_pogo(mitm_mapper=self._mitm_mapper):
                # TODO: put in loop, count up for a reboot ;)
                raise InternalStopWorkerException

    def __update_injection_settings(self):
        injected_settings = {}

        # don't try catch here, the injection settings update is called in the main loop anyway...
        routemanager_mode = self._mapping_manager.routemanager_get_mode(self._routemanager_name)

        ids_iv = []
        if routemanager_mode is None:
            # worker has to sleep, just empty out the settings...
            ids_iv = []
            scanmode = "nothing"
        elif routemanager_mode == "mon_mitm":
            scanmode = "mons"
            routemanager_settings = self._mapping_manager.routemanager_get_settings(self._routemanager_name)
            if routemanager_settings is not None:
                ids_iv = self._mapping_manager.get_monlist(routemanager_settings.get("mon_ids_iv", None),
                                                           self._routemanager_name)
        elif routemanager_mode == "raids_mitm":
            scanmode = "raids"
            routemanager_settings = self._mapping_manager.routemanager_get_settings(self._routemanager_name)
            if routemanager_settings is not None:
                ids_iv = self._mapping_manager.get_monlist(routemanager_settings.get("mon_ids_iv", None),
                                                           self._routemanager_name)
        elif routemanager_mode == "iv_mitm":
            scanmode = "ivs"
            ids_iv = self._mapping_manager.routemanager_get_encounter_ids_left(self._routemanager_name)
        else:
            # TODO: should we throw an exception here?
            ids_iv = []
            scanmode = "nothing"
        injected_settings["scanmode"] = scanmode

        # if iv ids are specified we will sync the workers encountered ids to newest time.
        if ids_iv:
            (self._latest_encounter_update, encounter_ids) = self._db_wrapper.update_encounters_from_db(
                self._mapping_manager.routemanager_get_geofence_helper(self._routemanager_name),
                self._latest_encounter_update)
            if encounter_ids:
                self.logger.debug("Found {} new encounter_ids", len(encounter_ids))
            self._encounter_ids = {**encounter_ids, **self._encounter_ids}
            # allow one minute extra life time, because the clock on some devices differs, newer got why this problem
            # apears but it is a fact.
            max_age = time.time() - 60

            remove = []
            for key, value in self._encounter_ids.items():
                if value < max_age:
                    remove.append(key)

            for key in remove:
                del self._encounter_ids[key]

            self.logger.debug("Encounter list len: {}", len(self._encounter_ids))
            # TODO: here we have the latest update of encountered mons.
            # self._encounter_ids contains the complete dict.
            # encounter_ids only contains the newest update.
        self._mitm_mapper.update_latest(origin=self._origin, key="ids_encountered", values_dict=self._encounter_ids)
        self._mitm_mapper.update_latest(origin=self._origin, key="ids_iv", values_dict=ids_iv)
        self._mitm_mapper.update_latest(origin=self._origin, key="injected_settings", values_dict=injected_settings)

    def _check_for_data_content(self, latest_data, proto_to_wait_for: int, timestamp: float) \
            -> Tuple[LatestReceivedType, Optional[object]]:
        type_of_data_found: LatestReceivedType = LatestReceivedType.UNDEFINED
        data_found: Optional[object] = None
        latest_proto_entry = latest_data.get(proto_to_wait_for, None)
        if not latest_proto_entry:
            self.logger.debug("No data linked to the requested proto since MAD started.")
            return type_of_data_found, data_found

        # proto has previously been received, let's check the timestamp...
        mode = self._mapping_manager.routemanager_get_mode(self._routemanager_name)
        timestamp_of_proto: float = latest_proto_entry.get("timestamp", None)
        self.logger.debug("Latest timestamp: {} vs. timestamp waited for: {} of proto {}",
                          datetime.fromtimestamp(timestamp_of_proto), datetime.fromtimestamp(timestamp),
                          proto_to_wait_for)
        if timestamp_of_proto < timestamp:
            self.logger.debug("latest timestamp of proto {} ({}) is older than {}", proto_to_wait_for,
                              timestamp_of_proto, timestamp)
            # TODO: timeout error instead of data_error_counter? Differentiate timeout vs missing data (the
            # TODO: latter indicates too high speeds for example
            return type_of_data_found, data_found

        latest_proto_data: dict = latest_proto_entry.get("values", None)
        if latest_proto_data is None:
            return LatestReceivedType.UNDEFINED, data_found
        location_of_proto = latest_proto_data.get("location", None)
        latest_proto = latest_proto_data.get("payload")
        # check if the location of the proto is close to the worker location... no need to check if a location is
        # present since that has been checked by MITMBase (mhm, spaghetti)
        if not location_of_proto and not self._check_data_distance(latest_proto['cells']):
            self.logger.debug("GMO is out of range (determined by checking the cells contained in the GMO")
            return type_of_data_found, data_found
        if mode in ["mon_mitm", "iv_mitm"]:
            self.logger.debug("Checking GMO for mons")
            # Now check if there are wild mons...
            # TODO: Should we check if there are any spawnpoints? Wild mons could not be present in forests etc...
            amount_of_wild_mons: int = 0
            for cell in latest_proto['cells']:
                for wild_mon in cell.get("wild_pokemon"):
                    encounter_id: Optional[int] = wild_mon.get("encounter_id")
                    if encounter_id and encounter_id > 0:
                        amount_of_wild_mons += 1
            if amount_of_wild_mons > 0:
                data_found = latest_proto
                type_of_data_found = LatestReceivedType.GMO
            else:
                self.logger.debug("No wild mons in GMO")
        elif mode in ["raids_mitm"]:
            self.logger.debug("Checking GMO for forts")
            amount_of_forts: int = 0
            for cell in latest_proto['cells']:
                for fort in cell['forts']:
                    # if there's location in latest, the distance has
                    # already been checked in MITMBase
                    fort_id: Optional[int] = fort.get("id", None)
                    if fort_id and fort_id > 0:
                        amount_of_forts += 1
            if amount_of_forts > 0:
                data_found = latest_proto
                type_of_data_found = LatestReceivedType.GMO
            else:
                self.logger.debug("No forts in GMO")
        else:
            self.logger.warning("No mode specified to wait for - this should not even happen...")
            time.sleep(0.5)

        return type_of_data_found, data_found
