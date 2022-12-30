import asyncio
import math
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Set, Tuple, Union

from aioredis import Redis

from mapadroid.data_handler.mitm_data.holder.latest_mitm_data.LatestMitmDataEntry import \
    LatestMitmDataEntry
from mapadroid.db.helper.PokemonHelper import PokemonHelper
from mapadroid.mapping_manager.MappingManagerDevicemappingKey import \
    MappingManagerDevicemappingKey
from mapadroid.utils.collections import Location
from mapadroid.utils.DatetimeWrapper import DatetimeWrapper
from mapadroid.utils.geo import get_distance_of_two_points_in_meters
from mapadroid.utils.logging import LoggerEnums, get_logger
from mapadroid.utils.madGlobals import (FortSearchResultTypes,
                                        InternalStopWorkerException,
                                        TransportType)
from mapadroid.utils.ProtoIdentifier import ProtoIdentifier
from mapadroid.worker.ReceivedTypeEnum import ReceivedType
from mapadroid.worker.strategy.AbstractMitmBaseStrategy import \
    AbstractMitmBaseStrategy

logger = get_logger(LoggerEnums.worker)


class AbstractWorkerMitmStrategy(AbstractMitmBaseStrategy, ABC):
    @abstractmethod
    async def _check_for_data_content(self, latest: Optional[LatestMitmDataEntry],
                                      proto_to_wait_for: ProtoIdentifier,
                                      timestamp: int) -> Tuple[ReceivedType, Optional[object]]:
        pass

    async def pre_work_loop(self):
        await super().pre_work_loop()
        logger.info("MITM worker starting")
        await self.__update_injection_settings()

        if not await self._wait_for_injection() or self._worker_state.stop_worker_event.is_set():
            raise InternalStopWorkerException("Worker stopped in pre work loop")

        reached_main_menu = await self._check_pogo_main_screen(10, True)
        if not reached_main_menu:
            if not await self._restart_pogo():
                # TODO: put in loop, count up for a reboot ;)
                raise InternalStopWorkerException("Worker stopped in pre work loop")

    async def pre_location_update(self):
        await self.__update_injection_settings()

    async def move_to_location(self):
        distance, routemanager_settings = await self._get_route_manager_settings_and_distance_to_current_location()
        # TODO: Either remove routemanager from scan strategy in case we split apart everything or access init
        #  bool directly...
        speed = getattr(routemanager_settings, "speed", 0)
        max_distance = getattr(routemanager_settings, "max_distance", None)

        if (not speed or speed == 0 or
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
            logger.debug("main: Walking...")
            time_it_takes_to_walk = distance / (speed / 3.6)  # speed is in kmph , delay_used need mps
            logger.debug2("Walking {} m, this will take {} seconds", distance, time_it_takes_to_walk)
            await self._mapping_manager.routemanager_set_worker_sleeping(self._area_id,
                                                                         self._worker_state.origin,
                                                                         time_it_takes_to_walk)
            timestamp_to_use = await self._walk_to_location(speed)

            delay_used = await self.get_devicesettings_value(MappingManagerDevicemappingKey.POST_WALK_DELAY, 0)
        logger.debug2("Sleeping for {}s", delay_used)
        await self._mapping_manager.routemanager_set_worker_sleeping(self._area_id,
                                                                     self._worker_state.origin,
                                                                     delay_used)
        await asyncio.sleep(float(delay_used))
        await self.set_devicesettings_value(MappingManagerDevicemappingKey.LAST_LOCATION,
                                            self._worker_state.current_location)
        self._worker_state.last_location = self._worker_state.current_location
        return timestamp_to_use

    async def post_move_location_routine(self, timestamp) -> Optional[Tuple[ReceivedType,
                                                                            Optional[Union[dict,
                                                                                           FortSearchResultTypes]],
                                                                            float]]:
        # TODO: pass the appropriate proto number if IV?
        type_received, data_gmo, time_received = await self._wait_for_data(timestamp)
        if type_received != ReceivedType.GMO or not data_gmo:
            logger.warning("Worker failed getting data at {:.5f}, {:.5f}. Trying next location...",
                           self._worker_state.current_location.lat,
                           self._worker_state.current_location.lng)
            return None
        return type_received, data_gmo, time_received

    async def _gmo_contains_wild_mons_closeby(self, gmo) -> bool:
        cells = gmo.get("cells", None)
        if not cells:
            return False
        for cell in cells:
            for wild_mon in cell["wild_pokemon"]:
                lat = wild_mon["latitude"]
                lon = wild_mon["longitude"]
                distance_to_mon: float = get_distance_of_two_points_in_meters(lat, lon,
                                                                              self._worker_state.current_location.lat,
                                                                              self._worker_state.current_location.lng)
                # TODO: Distance probably incorrect
                if distance_to_mon > 70:
                    logger.debug("Distance to mon around considered to be too far away to await encounter")
                    continue
                else:
                    logger.debug2("Mon at {:.5f}, {:.5f} at distance {}", lat, lon, distance_to_mon)
                    return True
        return False

    async def _gmo_contains_mons_to_be_encountered(self, gmo, check_encounter_id: bool = False) -> bool:
        cells = gmo.get("cells", None)
        if not cells:
            return False
        ids_to_encounter: Set[int] = set()
        if not check_encounter_id:
            routemanager_settings = await self._mapping_manager.routemanager_get_settings(self._area_id)
            if routemanager_settings is not None:
                # TODO: Moving to async
                ids_iv = self._mapping_manager.get_monlist(self._area_id)
                ids_to_encounter = {id_to_encounter for id_to_encounter in ids_iv}
        else:
            ids_iv = await self._mapping_manager.routemanager_get_encounter_ids_left(self._area_id)
            ids_to_encounter = {id_to_encounter for id_to_encounter in ids_iv}

        for cell in cells:
            for wild_mon in cell["wild_pokemon"]:
                spawnid = int(str(wild_mon["spawnpoint_id"]), 16)
                lat = wild_mon["latitude"]
                lon = wild_mon["longitude"]
                distance_to_mon: float = get_distance_of_two_points_in_meters(lat, lon,
                                                                              self._worker_state.current_location.lat,
                                                                              self._worker_state.current_location.lng)
                # TODO: Distance probably incorrect
                if distance_to_mon > 65:
                    logger.debug("Distance to mon around considered to be too far away to await encounter")
                    continue
                # If the mon has been encountered before, continue as it cannot be expected to be encountered again
                encounter_id = wild_mon["encounter_id"]
                pokemon_data = wild_mon.get("pokemon_data")
                mon_id = pokemon_data.get("id")
                pokemon_display = pokemon_data.get("display", {})
                weather_boosted = pokemon_display.get('weather_boosted_value', None)
                if encounter_id < 0:
                    encounter_id = encounter_id + 2 ** 64
                cache_key = "moniv{}-{}-{}".format(encounter_id, weather_boosted, mon_id)
                cache: Redis = await self._db_wrapper.get_cache()
                if await cache.exists(cache_key):
                    continue
                if encounter_id in self._encounter_ids:
                    # already encountered
                    continue
                # now check whether mon_mitm's mon IDs to scan are present and unscanned
                # OR iv_mitm...
                if not check_encounter_id and mon_id in ids_to_encounter:
                    return True
                elif check_encounter_id and encounter_id in ids_to_encounter:
                    return True
        return False

    async def worker_specific_setup_start(self):
        pass

    async def worker_specific_setup_stop(self):
        pass

    @abstractmethod
    async def _get_ids_iv_and_scanmode(self) -> Tuple[List[int], str]:
        pass

    async def _get_unquest_stops(self) -> Set[str]:
        """
        Populate with stop IDs which already hold quests for the given area to be scanned
        Returns: Set of pokestop IDs which already hold a quest
        """
        return set()

    async def __update_injection_settings(self):
        injected_settings = {}

        ids_iv, scanmode = await self._get_ids_iv_and_scanmode()
        injected_settings["scanmode"] = scanmode

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
            encounter_ids_prepared: Dict[str, int] = {str(encounter_id): timestamp for encounter_id, timestamp in
                                                      encounter_ids.items()}
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
        unquest_stops: Union[List, Dict] = list(await self._get_unquest_stops())
        await self._mitm_mapper.update_latest(worker=self._worker_state.origin, key="ids_encountered",
                                              value=self._encounter_ids)
        await self._mitm_mapper.update_latest(worker=self._worker_state.origin, key="ids_iv", value=ids_iv)
        await self._mitm_mapper.update_latest(worker=self._worker_state.origin, key="unquest_stops",
                                              value=unquest_stops)
        await self._mitm_mapper.update_latest(worker=self._worker_state.origin, key="injected_settings",
                                              value=injected_settings)
