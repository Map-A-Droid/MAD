import math
import time
from datetime import datetime
from typing import Union

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
        self._wait_for_data(timestamp)

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

            delay_used = self.get_devicesettings_value('post_teleport_delay', 7)
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
            delay_used = self.get_devicesettings_value('post_walk_delay', 7)
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

    def _wait_data_worker(self, latest, proto_to_wait_for, timestamp):
        data_requested: Union[LatestReceivedType, dict] = LatestReceivedType.UNDEFINED
        if latest is None:
            self.logger.debug("Nothing received from since MAD started")
            time.sleep(0.5)
        elif proto_to_wait_for not in latest:
            self.logger.debug("No data linked to the requested proto since MAD started.")
            time.sleep(0.5)
        else:
            # proto has previously been received, let's check the timestamp...
            # TODO: int vs str-key?
            latest_proto = latest.get(proto_to_wait_for, None)

            mode = self._mapping_manager.routemanager_get_mode(self._routemanager_name)
            latest_timestamp = latest_proto.get("timestamp", 0)
            self.logger.debug("Latest timestamp: {} vs. timestamp waited for: {} of proto {}",
                              datetime.fromtimestamp(latest_timestamp), datetime.fromtimestamp(timestamp),
                              proto_to_wait_for)
            if latest_timestamp >= timestamp:
                # TODO: consider reseting timestamp here since we clearly received SOMETHING
                latest_data: dict = latest_proto.get("values", None)
                if latest_data is None:
                    time.sleep(0.5)
                    return LatestReceivedType.UNDEFINED
                elif mode in ["mon_mitm", "iv_mitm"]:
                    # check if the GMO contains mons
                    for data_extract in latest_data['payload']['cells']:
                        for pokemon in data_extract['wild_pokemon']:
                            # TODO: teach Prio Q / Clusterer to hold additional data such as mon/encounter IDs
                            # if there's location in latest, the distance has
                            # already been checked in MITMBase
                            valid_distance = self._check_data_distance(latest_data['payload']['cells'])
                            if pokemon['spawnpoint_id'] and (latest.get("location", None) or valid_distance):
                                data_requested = latest_data
                                break
                        if data_requested != LatestReceivedType.UNDEFINED:
                            break
                    if data_requested is None or data_requested == LatestReceivedType.UNDEFINED:
                        self.logger.debug("No spawnpoints in data requested")
                        time.sleep(1)
                elif mode in ["raids_mitm"]:
                    self.logger.debug("Checking raids_mitm data")
                    for data_extract in latest_data['payload']['cells']:
                        for forts in data_extract['forts']:
                            # if there's location in latest, the distance has
                            # already been checked in MITMBase
                            if forts['id'] and (latest.get("location", None) or
                                                self._check_data_distance(latest_data['payload']['cells'])):
                                self.logger.debug("Got proper fort data for raids")
                                data_requested = latest_data
                                break
                        if data_requested != LatestReceivedType.UNDEFINED:
                            break
                    if data_requested is None or data_requested == LatestReceivedType.UNDEFINED:
                        self.logger.debug("No forts in data received: {}", latest_data)
                        time.sleep(0.5)
                    else:
                        self.logger.debug("Got data requested: {}", data_requested)
                else:
                    self.logger.warning("No mode specified to wait for - this should not even happen...")
                    time.sleep(0.5)
            else:
                self.logger.debug("latest timestamp of proto {} ({}) is older than {}", proto_to_wait_for,
                                  latest_timestamp, timestamp)
                # TODO: timeout error instead of data_error_counter? Differentiate timeout vs missing data (the
                # TODO: latter indicates too high speeds for example
                time.sleep(0.5)
        return data_requested
