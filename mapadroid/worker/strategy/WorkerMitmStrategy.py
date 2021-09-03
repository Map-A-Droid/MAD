import asyncio
import math
import time
from typing import Dict, Union, Tuple, Optional, List

from mapadroid.data_handler.mitm_data.holder.latest_mitm_data.LatestMitmDataEntry import LatestMitmDataEntry
from mapadroid.db.helper.PokemonHelper import PokemonHelper
from mapadroid.mapping_manager.MappingManagerDevicemappingKey import MappingManagerDevicemappingKey
from mapadroid.utils.DatetimeWrapper import DatetimeWrapper
from mapadroid.utils.ProtoIdentifier import ProtoIdentifier
from mapadroid.utils.collections import Location
from mapadroid.utils.madGlobals import TransportType, InternalStopWorkerException
from mapadroid.worker.ReceivedTypeEnum import ReceivedType
from mapadroid.worker.WorkerType import WorkerType
from mapadroid.worker.strategy.AbstractMitmBaseStrategy import AbstractMitmBaseStrategy
from loguru import logger


class WorkerMitmStrategy(AbstractMitmBaseStrategy):
    async def _check_for_data_content(self, latest: Dict[str, LatestMitmDataEntry],
                                      proto_to_wait_for: ProtoIdentifier,
                                      timestamp: int) -> Tuple[ReceivedType, Optional[object]]:
        type_of_data_found: ReceivedType = ReceivedType.UNDEFINED
        data_found: Optional[object] = None
        latest_proto_entry: Optional[LatestMitmDataEntry] = latest.get(str(proto_to_wait_for.value), None)
        if not latest_proto_entry:
            logger.debug("No data linked to the requested proto since MAD started.")
            return type_of_data_found, data_found

        # proto has previously been received, let's check the timestamp...
        mode = await self._mapping_manager.routemanager_get_mode(self._area_id)
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
            return ReceivedType.UNDEFINED, data_found
        key_to_check: str = "wild_pokemon" if mode in [WorkerType.MON_MITM.value, WorkerType.IV_MITM.value] else "forts"
        if self._gmo_cells_contain_multiple_of_key(latest_proto_data, key_to_check):
            data_found = latest_proto_data
            type_of_data_found = ReceivedType.GMO
        else:
            logger.debug("{} not in GMO", key_to_check)

        return type_of_data_found, data_found

    async def pre_work_loop(self):
        await super().pre_work_loop()
        logger.info("MITM worker starting")
        await self.__update_injection_settings()

        if not await self._wait_for_injection() or self._worker_state.stop_worker_event.is_set():
            raise InternalStopWorkerException

        reached_main_menu = await self._check_pogo_main_screen(10, True)
        if not reached_main_menu:
            if not await self._restart_pogo(mitm_mapper=self._mitm_mapper):
                # TODO: put in loop, count up for a reboot ;)
                raise InternalStopWorkerException

    async def pre_location_update(self):
        await self.__update_injection_settings()

    async def move_to_location(self):
        distance, routemanager_settings = await self._get_route_manager_settings_and_distance_to_current_location()
        # TODO: Either remove routemanager from scan strategy in case we split apart everything or access init
        #  bool directly...
        if not await self._mapping_manager.routemanager_get_init(self._area_id):
            speed = getattr(routemanager_settings, "speed", 0)
            max_distance = getattr(routemanager_settings, "max_distance", None)
        else:
            speed = int(25)
            max_distance = int(200)

        if (speed == 0 or
                (max_distance and 0 < max_distance < distance) or
                (self._worker_state.last_location.lat == 0.0 and self._worker_state.last_location.lng == 0.0)):
            logger.debug("main: Teleporting...")
            self._worker_state.last_transport_type = TransportType.TELEPORT
            await self._communicator.set_location(
                Location(self._worker_state.current_location.lat, self._worker_state.current_location.lng), 0)
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
        await self.set_devicesettings_value(MappingManagerDevicemappingKey.LAST_LOCATION,
                                            self._worker_state.current_location)
        self._worker_state.last_location = self._worker_state.current_location
        return timestamp_to_use, True

    async def post_move_location_routine(self, timestamp):
        # TODO: pass the appropriate proto number if IV?
        type_received, data = await self._wait_for_data(timestamp)
        if type_received != ReceivedType.GMO:
            logger.warning("Worker failed to retrieve proper data at {}, {}. Worker will continue with "
                           "the next location",
                           self._worker_state.current_location.lat,
                           self._worker_state.current_location.lng)

    async def worker_specific_setup_start(self):
        pass

    async def worker_specific_setup_stop(self):
        pass

    async def __update_injection_settings(self):
        injected_settings = {}

        # don't try catch here, the injection settings update is called in the main loop anyway...
        routemanager_mode = await self._mapping_manager.routemanager_get_mode(self._area_id)

        ids_iv = []
        if routemanager_mode is None:
            # worker has to sleep, just empty out the settings...
            ids_iv = []
            scanmode = "nothing"
        elif routemanager_mode == WorkerType.MON_MITM:
            scanmode = "mons"
            routemanager_settings = await self._mapping_manager.routemanager_get_settings(self._area_id)
            if routemanager_settings is not None:
                # TODO: Moving to async
                ids_iv = self._mapping_manager.get_monlist(self._area_id)
        elif routemanager_mode == WorkerType.RAID_MITM:
            scanmode = "raids"
            routemanager_settings = await self._mapping_manager.routemanager_get_settings(self._area_id)
            if routemanager_settings is not None:
                # TODO: Moving to async
                ids_iv = self._mapping_manager.get_monlist(self._area_id)
        elif routemanager_mode == WorkerType.IV_MITM:
            scanmode = "ivs"
            ids_iv = await self._mapping_manager.routemanager_get_encounter_ids_left(self._area_id)
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
                    await self._mapping_manager.routemanager_get_geofence_helper(self._area_id),
                    self._latest_encounter_update)
            if encounter_ids:
                logger.debug("Found {} new encounter_ids", len(encounter_ids))
            # str keys since protobuf requires string keys for json...
            encounter_ids_prepared: Dict[str, int] = { str(encounter_id): timestamp for encounter_id, timestamp in encounter_ids.items() }
            self._encounter_ids: Dict[str, int] = {**encounter_ids_prepared, **self._encounter_ids}
            # allow one minute extra life time, because the clock on some devices differs, newer got why this problem
            # apears but it is a fact.
            max_age_ = DatetimeWrapper.now().timestamp()
            remove: List[str] = []
            for key, value in self._encounter_ids.items():
                if int(value) < max_age_:
                    remove.append(key)

            for key in remove:
                del self._encounter_ids[key]

            logger.debug("Encounter list len: {}", len(self._encounter_ids))
            # TODO: here we have the latest update of encountered mons.
            # self._encounter_ids contains the complete dict.
            # encounter_ids only contains the newest update.
        await self._mitm_mapper.update_latest(worker=self._worker_state.origin, key="ids_encountered",
                                              value=self._encounter_ids)
        await self._mitm_mapper.update_latest(worker=self._worker_state.origin, key="ids_iv", value=ids_iv)
        await self._mitm_mapper.update_latest(worker=self._worker_state.origin, key="unquest_stops",
                                              value=self.unquestStops)
        await self._mitm_mapper.update_latest(worker=self._worker_state.origin, key="injected_settings",
                                              value=injected_settings)
