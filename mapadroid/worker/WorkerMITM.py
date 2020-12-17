import math
import time
from datetime import datetime
from typing import Tuple, Optional

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.mitm_receiver.MitmMapper import MitmMapper
from mapadroid.ocr.pogoWindows import PogoWindows
from mapadroid.utils import MappingManager
from mapadroid.utils.ProtoIdentifier import ProtoIdentifier
from mapadroid.utils.collections import Location
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
        type_received, data = self._wait_for_data(timestamp)
        if type_received != LatestReceivedType.GMO:
            self.logger.warning("Worker failed to retrieve proper data at {}, {}. Worker will continue with "
                                "the next location", self.current_location.lat, self.current_location.lng)

    def _move_to_location(self):
        distance, routemanager_settings = self._get_route_manager_settings_and_distance_to_current_location()

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
            timestamp_to_use = math.floor(time.time())

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
                self._walk_after_teleport(walk_distance_post_teleport)
        else:
            self.logger.info("main: Walking...")
            timestamp_to_use = self._walk_to_location(speed)

            delay_used = self.get_devicesettings_value('post_walk_delay', 0)
        self.logger.debug2("Sleeping for {}s", delay_used)
        time.sleep(float(delay_used))
        self.set_devicesettings_value("last_location", self.current_location)
        self.last_location = self.current_location
        self._waittime_without_delays = time.time()
        return timestamp_to_use, True

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

        # getting unprocessed stops (without quest)
        self.unquestStops = self._db_wrapper.stop_from_db_without_quests(
            self._mapping_manager.routemanager_get_geofence_helper(self._routemanager_name),
            latlng=False)

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
        self._mitm_mapper.update_latest(origin=self._origin, key="unquest_stops", values_dict=self.unquestStops)
        self._mitm_mapper.update_latest(origin=self._origin, key="injected_settings", values_dict=injected_settings)

    def _check_for_data_content(self, latest_data, proto_to_wait_for: ProtoIdentifier, timestamp: float) \
            -> Tuple[LatestReceivedType, Optional[object]]:
        type_of_data_found: LatestReceivedType = LatestReceivedType.UNDEFINED
        data_found: Optional[object] = None
        latest_proto_entry = latest_data.get(proto_to_wait_for.value, None)
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
        latest_proto = latest_proto_data.get("payload")
        key_to_check: str = "wild_pokemon" if mode in ["mon_mitm", "iv_mitm"] else "forts"
        if self._gmo_cells_contain_multiple_of_key(latest_proto, key_to_check):
            data_found = latest_proto
            type_of_data_found = LatestReceivedType.GMO
        else:
            self.logger.debug("{} not in GMO", key_to_check)

        return type_of_data_found, data_found
