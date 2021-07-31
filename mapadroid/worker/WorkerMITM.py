import asyncio
import math
import time
from typing import Optional, Tuple

from loguru import logger

from mapadroid.data_handler.MitmMapper import MitmMapper
from mapadroid.data_handler.mitm_data.holder.latest_mitm_data.LatestMitmDataEntry import LatestMitmDataEntry
from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.helper.PokemonHelper import PokemonHelper
from mapadroid.db.model import SettingsWalkerarea
from mapadroid.mapping_manager import MappingManager
from mapadroid.mapping_manager.MappingManagerDevicemappingKey import MappingManagerDevicemappingKey
from mapadroid.ocr.pogoWindows import PogoWindows
from mapadroid.utils.DatetimeWrapper import DatetimeWrapper
from mapadroid.utils.ProtoIdentifier import ProtoIdentifier
from mapadroid.utils.collections import Location
from mapadroid.utils.madGlobals import InternalStopWorkerException, TransportType
from mapadroid.websocket.AbstractCommunicator import AbstractCommunicator
from mapadroid.worker.MITMBase import LatestReceivedType, MITMBase
from mapadroid.worker.WorkerType import WorkerType


class WorkerMITM(MITMBase):
    def __init__(self, args, dev_id, origin, last_known_state, communicator: AbstractCommunicator,
                 mapping_manager: MappingManager, area_id: int, routemanager_id: int, mitm_mapper: MitmMapper,
                 db_wrapper: DbWrapper, pogo_window_manager: PogoWindows, walker: SettingsWalkerarea, event):
        MITMBase.__init__(self, args, dev_id, origin, last_known_state, communicator,
                          mapping_manager=mapping_manager, area_id=area_id,
                          routemanager_id=routemanager_id,
                          db_wrapper=db_wrapper,
                          mitm_mapper=mitm_mapper, pogo_window_manager=pogo_window_manager, walker=walker, event=event)

    async def start_worker(self):
        # TODO: own InjectionSettings class
        await self.__update_injection_settings()
        await super().start_worker()

    async def _health_check(self):
        logger.debug4("_health_check: called")

    async def _cleanup(self):
        # no additional cleanup in MITM yet
        pass

    async def _post_move_location_routine(self, timestamp):
        # TODO: pass the appropriate proto number if IV?
        type_received, data = await self._wait_for_data(timestamp)
        if type_received != LatestReceivedType.GMO:
            logger.warning("Worker failed to retrieve proper data at {}, {}. Worker will continue with "
                           "the next location", self.current_location.lat, self.current_location.lng)

    async def _move_to_location(self):
        distance, routemanager_settings = await self._get_route_manager_settings_and_distance_to_current_location()
        if not await self._mapping_manager.routemanager_get_init(self._routemanager_id):
            speed = getattr(routemanager_settings, "speed", 0)
            max_distance = getattr(routemanager_settings, "max_distance", None)
        else:
            speed = int(25)
            max_distance = int(200)

        if (speed == 0 or
                (max_distance and 0 < max_distance < distance) or
                (self.last_location.lat == 0.0 and self.last_location.lng == 0.0)):
            logger.debug("main: Teleporting...")
            self._transporttype = TransportType.TELEPORT
            await self._communicator.set_location(
                Location(self.current_location.lat, self.current_location.lng), 0)
            # the time we will take as a starting point to wait for data...
            timestamp_to_use = math.floor(time.time())

            delay_used = await self.get_devicesettings_value(MappingManagerDevicemappingKey.POST_TELEPORT_DELAY, 0)
            # Test for cooldown / teleported distance TODO: check this block...
            if await self.get_devicesettings_value(MappingManagerDevicemappingKey.COOLDOWN_SLEEP, False):
                if distance > 10000:
                    delay_used = 15
                elif distance > 5000:
                    delay_used = 10
                elif distance > 2500:
                    delay_used = 8
                logger.debug("Need more sleep after Teleport: {} seconds!", delay_used)
            walk_distance_post_teleport = await self.get_devicesettings_value(
                MappingManagerDevicemappingKey.WALK_AFTER_TELEPORT_DISTANCE, 0)
            if 0 < walk_distance_post_teleport < distance:
                await self._walk_after_teleport(walk_distance_post_teleport)
        else:
            logger.info("main: Walking...")
            timestamp_to_use = await self._walk_to_location(speed)

            delay_used = await self.get_devicesettings_value(MappingManagerDevicemappingKey.POST_WALK_DELAY, 0)
        logger.debug2("Sleeping for {}s", delay_used)
        await asyncio.sleep(float(delay_used))
        await self.set_devicesettings_value(MappingManagerDevicemappingKey.LAST_LOCATION, self.current_location)
        self.last_location = self.current_location
        self._waittime_without_delays = time.time()
        return timestamp_to_use, True

    async def _pre_location_update(self):
        await self.__update_injection_settings()

    async def _pre_work_loop(self):
        logger.info("MITM worker starting")
        if not await self._wait_for_injection() or self._stop_worker_event.is_set():
            raise InternalStopWorkerException

        reached_main_menu = await self._check_pogo_main_screen(10, True)
        if not reached_main_menu:
            if not await self._restart_pogo(mitm_mapper=self._mitm_mapper):
                # TODO: put in loop, count up for a reboot ;)
                raise InternalStopWorkerException

    async def __update_injection_settings(self):
        injected_settings = {}

        # don't try catch here, the injection settings update is called in the main loop anyway...
        routemanager_mode = await self._mapping_manager.routemanager_get_mode(self._routemanager_id)

        ids_iv = []
        if routemanager_mode is None:
            # worker has to sleep, just empty out the settings...
            ids_iv = []
            scanmode = "nothing"
        elif routemanager_mode == WorkerType.MON_MITM:
            scanmode = "mons"
            routemanager_settings = await self._mapping_manager.routemanager_get_settings(self._routemanager_id)
            if routemanager_settings is not None:
                # TODO: Moving to async
                ids_iv = self._mapping_manager.get_monlist(self._routemanager_id)
        elif routemanager_mode == WorkerType.RAID_MITM:
            scanmode = "raids"
            routemanager_settings = await self._mapping_manager.routemanager_get_settings(self._routemanager_id)
            if routemanager_settings is not None:
                # TODO: Moving to async
                ids_iv = self._mapping_manager.get_monlist(self._routemanager_id)
        elif routemanager_mode == WorkerType.IV_MITM:
            scanmode = "ivs"
            ids_iv = await self._mapping_manager.routemanager_get_encounter_ids_left(self._routemanager_id)
        else:
            # TODO: should we throw an exception here?
            ids_iv = []
            scanmode = "nothing"
        injected_settings["scanmode"] = scanmode

        # getting unprocessed stops (without quest)
        self.unquestStops = []

        # if iv ids are specified we will sync the workers encountered ids to newest time.
        if ids_iv:
            async with self._db_wrapper as session, session:
                (self._latest_encounter_update, encounter_ids) = await PokemonHelper.get_encountered(
                    session,
                    await self._mapping_manager.routemanager_get_geofence_helper(self._routemanager_id),
                    self._latest_encounter_update)
            if encounter_ids:
                logger.debug("Found {} new encounter_ids", len(encounter_ids))
            self._encounter_ids = {**encounter_ids, **self._encounter_ids}
            # allow one minute extra life time, because the clock on some devices differs, newer got why this problem
            # apears but it is a fact.
            max_age_ = DatetimeWrapper.now().timestamp()
            remove = []
            for key, value in self._encounter_ids.items():
                if value < max_age_:
                    remove.append(key)

            for key in remove:
                del self._encounter_ids[key]

            logger.debug("Encounter list len: {}", len(self._encounter_ids))
            # TODO: here we have the latest update of encountered mons.
            # self._encounter_ids contains the complete dict.
            # encounter_ids only contains the newest update.
        await self._mitm_mapper.update_latest(worker=self._origin, key="ids_encountered",
                                              value=self._encounter_ids)
        await self._mitm_mapper.update_latest(worker=self._origin, key="ids_iv", value=ids_iv)
        await self._mitm_mapper.update_latest(worker=self._origin, key="unquest_stops", value=self.unquestStops)
        await self._mitm_mapper.update_latest(worker=self._origin, key="injected_settings",
                                              value=injected_settings)

    async def _check_for_data_content(self, latest_data, proto_to_wait_for: ProtoIdentifier, timestamp: int) \
            -> Tuple[LatestReceivedType, Optional[object]]:
        type_of_data_found: LatestReceivedType = LatestReceivedType.UNDEFINED
        data_found: Optional[object] = None
        latest_proto_entry: Optional[LatestMitmDataEntry] = latest_data.get(proto_to_wait_for.value, None)
        if not latest_proto_entry:
            logger.debug("No data linked to the requested proto since MAD started.")
            return type_of_data_found, data_found

        # proto has previously been received, let's check the timestamp...
        mode = await self._mapping_manager.routemanager_get_mode(self._routemanager_id)
        timestamp_of_proto: int = latest_proto_entry.timestamp_of_data_retrieval
        logger.debug("Latest timestamp: {} vs. timestamp waited for: {} of proto {}",
                     DatetimeWrapper.fromtimestamp(timestamp_of_proto), DatetimeWrapper.fromtimestamp(timestamp),
                     proto_to_wait_for)
        if timestamp_of_proto < timestamp:
            logger.debug("latest timestamp of proto {} ({}) is older than {}", proto_to_wait_for,
                         timestamp_of_proto, timestamp)
            # TODO: timeout error instead of data_error_counter? Differentiate timeout vs missing data (the
            # TODO: latter indicates too high speeds for example
            return type_of_data_found, data_found

        latest_proto_data: dict = latest_proto_entry.data
        if latest_proto_data is None:
            return LatestReceivedType.UNDEFINED, data_found
        key_to_check: str = "wild_pokemon" if mode in [WorkerType.MON_MITM.value, WorkerType.IV_MITM.value] else "forts"
        if self._gmo_cells_contain_multiple_of_key(latest_proto_data, key_to_check):
            data_found = latest_proto_data
            type_of_data_found = LatestReceivedType.GMO
        else:
            logger.debug("{} not in GMO", key_to_check)

        return type_of_data_found, data_found
