import asyncio
import time
from datetime import datetime
from typing import List, Tuple, Optional, Union

import sqlalchemy
from loguru import logger
from redis import Redis

from mapadroid.cache import NoopCache
from mapadroid.data_handler.AbstractMitmMapper import AbstractMitmMapper
from mapadroid.db.DbPogoProtoSubmit import DbPogoProtoSubmit
from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.utils.DatetimeWrapper import DatetimeWrapper
from mapadroid.utils.madGlobals import MitmReceiverRetry, MonSeenTypes


class SerializedMitmDataProcessor:
    def __init__(self, data_queue: asyncio.Queue, application_args, mitm_mapper: AbstractMitmMapper,
                 db_wrapper: DbWrapper, name=None):
        self.__queue: asyncio.Queue = data_queue
        self.__db_wrapper: DbWrapper = db_wrapper
        # TODO: Init DbPogoProtoSubmit per processing passing session to constructor
        self.__db_submit: DbPogoProtoSubmit = db_wrapper.proto_submit
        self.__application_args = application_args
        self.__mitm_mapper: AbstractMitmMapper = mitm_mapper
        self.__name = name

    async def run(self):
        logger.info("Starting serialized MITM data processor")
        # TODO: use event to stop... Remove try/catch...
        with logger.contextualize(identifier=self.__name, name="mitm-processor"):
            while True:
                try:
                    item = await self.__queue.get()
                    if item is None:
                        logger.info("Received signal to stop MITM data processor")
                        break
                    start_time = self.get_time_ms()
                    try:
                        with logger.contextualize(identifier=item[2], name="mitm-processor"):
                            await self.process_data(received_timestamp=item[0], data=item[1],
                                                    origin=item[2])
                        del item
                    except (sqlalchemy.exc.IntegrityError, MitmReceiverRetry, sqlalchemy.exc.InternalError) as e:
                        logger.info("Failed submitting data to DB, rescheduling. {}", e)
                        await self.__queue.put(item)
                    except Exception as e:
                        logger.exception(e)
                        logger.info("Failed processing data. {}", e)
                    self.__queue.task_done()
                    end_time = self.get_time_ms() - start_time
                    logger.debug("MITM data processor {} finished queue item in {}ms", self.__name, end_time)
                except KeyboardInterrupt:
                    logger.info("Received keyboard interrupt, stopping MITM data processor")

    # @logger.catch
    async def process_data(self, received_timestamp: int, data, origin):
        data_type = data.get("type", None)
        logger.debug("Processing received data")
        processed_timestamp: datetime = DatetimeWrapper.fromtimestamp(received_timestamp)

        if data_type and not data.get("raw", False):
            logger.debug4("Received data: {}", data)
            threshold_seconds = self.__application_args.mitm_ignore_proc_time_thresh

            start_time = self.get_time_ms()
            if threshold_seconds > 0:
                minimum_timestamp = (start_time / 1000) - threshold_seconds
                if received_timestamp < minimum_timestamp:
                    logger.debug(
                        "Data received at {} is older than configured threshold of {}s ({}). Ignoring data.",
                        processed_timestamp, threshold_seconds, DatetimeWrapper.fromtimestamp(minimum_timestamp))
                    return

            # We can use the current session easily...
            if data_type == 106:
                await self.__process_gmo(data, origin, processed_timestamp, received_timestamp, start_time)
            elif data_type == 102:
                await self.__process_encounter(data, origin, processed_timestamp, received_timestamp, start_time)
            elif data_type == 145:
                # lure mons with iv
                await self.__process_lured_encounter(data, origin, processed_timestamp, received_timestamp, start_time)
            elif data_type == 101:
                logger.debug("Processing proto 101 (FORT_SEARCH)")
                async with self.__db_wrapper as session, session:
                    try:
                        new_quest: bool = await self.__db_submit.quest(session, data["payload"])
                        if new_quest:
                            await self.__mitm_mapper.stats_collect_quest(origin, processed_timestamp)
                        await session.commit()
                    except Exception as e:
                        logger.warning("Failed submitting quests to DB: {}", e)

                end_time = self.get_time_ms() - start_time
                logger.debug("Done processing proto 101 in {}ms", end_time)
            elif data_type == 104:
                logger.debug("Processing proto 104 (FORT_DETAILS)")
                async with self.__db_wrapper as session, session:
                    try:
                        await self.__db_submit.stop_details(session, data["payload"])
                        await session.commit()
                    except Exception as e:
                        logger.warning("Failed fort details to DB: {}", e)

                end_time = self.get_time_ms() - start_time
                logger.debug("Done processing proto 104 in {}ms", end_time)
            elif data_type == 4:
                logger.debug("Processing proto 4 (GET_HOLO_INVENTORY)")
                await self._handle_inventory_data(origin, data["payload"])
                end_time = self.get_time_ms() - start_time
                logger.debug("Done processing proto 4 in {}ms", end_time)
            elif data_type == 156:
                logger.debug("Processing proto 156 (GYM_GET_INFO)")
                async with self.__db_wrapper as session, session:
                    try:
                        await self.__db_submit.gym(session, data["payload"])
                        await session.commit()
                    except Exception as e:
                        logger.warning("Failed submitting gym info to DB: {}", e)

                end_time = self.get_time_ms() - start_time
                logger.debug("Done processing proto 156 in {}ms", end_time)

    async def __process_lured_encounter(self, data, origin, processed_timestamp, received_timestamp, start_time):
        playerlevel = await self.__mitm_mapper.get_level(origin)
        if self.__application_args.scan_lured_mons and (playerlevel >= 30):
            logger.debug("Processing lure encounter received at {}", processed_timestamp)

            async with self.__db_wrapper as session, session:
                lure_encounter: Optional[Tuple[int, datetime]] = await self.__db_submit \
                    .mon_lure_iv(session, received_timestamp, data["payload"])

                if self.__application_args.game_stats:
                    await self.__db_submit.update_seen_type_stats(session, lure_encounter=[lure_encounter])
                await session.commit()
            end_time = self.get_time_ms() - start_time
            logger.debug("Done processing lure encounter in {}ms", end_time)

    async def __process_encounter(self, data, origin, received_date: datetime, received_timestamp: int, start_time):
        # TODO: Cache result in SerializedMitmDataProcessor to not spam the MITMMapper too much in that regard
        playerlevel = await self.__mitm_mapper.get_level(origin)
        if playerlevel >= 30:
            logger.debug("Processing encounter received at {}", received_date)
            async with self.__db_wrapper as session, session:
                encounter: Optional[Tuple[int, bool]] = await self.__db_submit.mon_iv(session,
                                                                                      received_timestamp,
                                                                                      data["payload"])
            if self.__application_args.game_stats and encounter:
                encounter_id, is_shiny = encounter
                loop = asyncio.get_running_loop()
                loop.create_task(self.__mitm_mapper.stats_collect_mon_iv(origin, encounter_id, received_date, is_shiny))
            end_time = self.get_time_ms() - start_time
            logger.debug("Done processing encounter in {}ms", end_time)
        else:
            logger.warning("Playerlevel lower than 30 - not processing encounter IVs")

    async def __process_gmo(self, data, origin, received_date: datetime, received_timestamp: int, start_time):
        logger.info("Processing GMO. Received at {}", received_date)
        loop = asyncio.get_running_loop()
        weather_task = loop.create_task(self.__process_weather(data, received_timestamp))
        stops_task = loop.create_task(self.__process_stops(data))
        gyms_task = loop.create_task(self.__process_gyms(data))
        raids_task = loop.create_task(self.__process_raids(data))
        spawnpoints_task = loop.create_task(self.__process_spawnpoints(data, received_timestamp))
        cells_task = loop.create_task(self.__process_cells(data))
        mons_task = loop.create_task(self.__process_wild_mons(data, received_timestamp))

        gmo_loc_start = self.get_time_ms()
        gmo_loc_time = self.get_time_ms() - gmo_loc_start
        lure_encounter_ids: List[int] = []
        lure_no_iv_task = None
        if self.__application_args.scan_lured_mons:
            lure_no_iv_task = loop.create_task(self.__process_lure_no_iv(data, received_timestamp))
        lure_processing_time = 0

        nearby_task = None
        if self.__application_args.scan_nearby_mons:
            nearby_task = loop.create_task(self.__process_nearby_mons(data, received_timestamp))
        nearby_cell_encounter_ids = []
        nearby_stop_encounter_ids = []
        nearby_mons_time = 0
        wild_encounter_ids_in_gmo, wild_mon_processing_time = await mons_task
        if nearby_task:
            cell_encounters, stop_encounters, nearby_mons_time = await nearby_task
        if lure_no_iv_task:
            lure_encounter_ids, lure_processing_time = await lure_no_iv_task

        weather_time = await weather_task
        raids_time = await raids_task
        spawnpoints_time = await spawnpoints_task
        cells_time = await cells_task
        stops_time = await stops_task
        gyms_time = await gyms_task
        full_time = self.get_time_ms() - start_time
        logger.debug("Done processing GMO in {}ms (weather={}ms, stops={}ms, gyms={}ms, raids={}ms, " +
                     "spawnpoints={}ms, mons={}ms, "
                     "nearby_mons={}ms, lure_noiv={}ms, cells={}ms, "
                     "gmo_loc={}ms)",
                     full_time, weather_time, stops_time, gyms_time, raids_time,
                     spawnpoints_time, wild_mon_processing_time, nearby_mons_time, lure_processing_time,
                     cells_time, gmo_loc_time)
        loop.create_task(self.__fire_stats_gmo_submission(origin, received_date,
                                                          wild_encounter_ids_in_gmo,
                                                          nearby_cell_encounter_ids,
                                                          nearby_stop_encounter_ids,
                                                          lure_encounter_ids))

    async def __fire_stats_gmo_submission(self, worker: str, time_received_raw: datetime,
                                          wild_mon_encounter_ids_in_gmo: List[int],
                                          nearby_cell_mons: List[int],
                                          nearby_fort_mons: List[int],
                                          lure_mons: List[int]):
        await self.__mitm_mapper.stats_collect_wild_mon(worker, wild_mon_encounter_ids_in_gmo, time_received_raw)
        await self.__mitm_mapper.stats_collect_seen_type(nearby_cell_mons, MonSeenTypes.nearby_cell, time_received_raw)
        await self.__mitm_mapper.stats_collect_seen_type(nearby_fort_mons, MonSeenTypes.nearby_stop, time_received_raw)
        await self.__mitm_mapper.stats_collect_seen_type(lure_mons, MonSeenTypes.lure_wild, time_received_raw)

    async def __process_gmo_mon_stats(self, cell_encounters, lure_wild, stop_encounters, wild_encounter_ids_processed):
        async with self.__db_wrapper as session, session:
            await self.__db_submit.update_seen_type_stats(session,
                                                          wild=wild_encounter_ids_processed,
                                                          lure_wild=lure_wild,
                                                          nearby_cell=cell_encounters,
                                                          nearby_stop=stop_encounters)
            await session.commit()

    async def __process_lure_no_iv(self, data, received_timestamp) -> Tuple[List[int], int]:
        lurenoiv_start = self.get_time_ms()
        async with self.__db_wrapper as session, session:
            try:
                lure_wild = await self.__db_submit.mon_lure_noiv(session, received_timestamp, data["payload"])
                await session.commit()
            except Exception as e:
                logger.warning("Failed submitting lure no iv: {}", e)
        lure_processing_time = self.get_time_ms() - lurenoiv_start
        return lure_wild, lure_processing_time

    async def __process_nearby_mons(self, data, received_timestamp) -> Tuple[List[int], List[int], int]:
        nearby_mons_time_start = self.get_time_ms()
        async with self.__db_wrapper as session, session:
            try:
                cell_encounters, stop_encounters = await self.__db_submit.mons_nearby(session, received_timestamp,
                                                                                      data["payload"])
                await session.commit()
            except Exception as e:
                logger.warning("Failed submitting nearby mons: {}", e)
        nearby_mons_time = self.get_time_ms() - nearby_mons_time_start
        return cell_encounters, stop_encounters, nearby_mons_time

    async def __process_wild_mons(self, data, received_timestamp) -> Tuple[List[int], int]:
        mons_time_start = self.get_time_ms()
        async with self.__db_wrapper as session, session:
            try:
                encounter_ids_in_gmo = await self.__db_submit.mons(session,
                                                                   received_timestamp,
                                                                   data["payload"])
                await session.commit()
            except Exception as e:
                logger.warning("Failed submitting wild mons: {}", e)
        mons_time = self.get_time_ms() - mons_time_start
        return encounter_ids_in_gmo, mons_time

    async def __process_cells(self, data):
        cells_time_start = self.get_time_ms()
        async with self.__db_wrapper as session, session:
            try:
                await self.__db_submit.cells(session, data["payload"])
            except Exception as e:
                logger.warning("Failed submitting cells: {}", e)
        cells_time = self.get_time_ms() - cells_time_start
        return cells_time

    async def __process_spawnpoints(self, data, received_timestamp: int):
        spawnpoints_time_start = self.get_time_ms()
        async with self.__db_wrapper as session, session:
            try:
                await self.__db_submit.spawnpoints(session, data["payload"], received_timestamp)
                await session.commit()
            except Exception as e:
                logger.warning("Failed submitting spawnpoints: {}", e)
        spawnpoints_time = self.get_time_ms() - spawnpoints_time_start
        return spawnpoints_time

    async def __process_raids(self, data):
        raids_time_start = self.get_time_ms()
        async with self.__db_wrapper as session, session:
            try:
                await self.__db_submit.raids(session, data["payload"])
                await session.commit()
            except Exception as e:
                logger.warning("Failed submitting raids: {}", e)
        raids_time = self.get_time_ms() - raids_time_start
        return raids_time

    async def __process_gyms(self, data):
        gyms_time_start = self.get_time_ms()
        # TODO: If return value False, rollback transaction?
        async with self.__db_wrapper as session, session:
            try:
                await self.__db_submit.gyms(session, data["payload"])
                await session.commit()
            except Exception as e:
                logger.warning("Failed submitting gyms: {}", e)
        gyms_time = self.get_time_ms() - gyms_time_start
        return gyms_time

    async def __process_stops(self, data):
        stops_time_start = self.get_time_ms()
        async with self.__db_wrapper as session, session:
            try:
                await self.__db_submit.stops(session, data["payload"])
                await session.commit()
            except Exception as e:
                logger.warning("Failed submitting stops: {}", e)
        stops_time = self.get_time_ms() - stops_time_start
        return stops_time

    async def __process_weather(self, data, received_timestamp):
        weather_time_start = self.get_time_ms()
        async with self.__db_wrapper as session, session:
            try:
                await self.__db_submit.weather(session, data["payload"], received_timestamp)
                await session.commit()
            except Exception as e:
                logger.warning("Failed submitting weather: {}", e)
        weather_time = self.get_time_ms() - weather_time_start
        return weather_time

    @staticmethod
    def get_time_ms():
        return int(time.time() * 1000)

    async def _handle_inventory_data(self, origin: str, data: dict) -> None:
        if 'inventory_delta' not in data:
            logger.debug2('gen_player_stats cannot generate new stats')
            return
        cache: Union[Redis, NoopCache] = await self.__db_wrapper.get_cache()
        cache_key: str = f"inv_data_{origin}_processed"
        if await cache.exists(cache_key):
            return
        stats = data['inventory_delta'].get("inventory_items", None)
        if len(stats) > 0:
            for data_inventory in stats:
                player_stats = data_inventory['inventory_item_data']['player_stats']
                player_level = player_stats['level']
                if int(player_level) > 0:
                    logger.debug2('{{gen_player_stats}} saving new playerstats')
                    await self.__mitm_mapper.set_level(origin, int(player_level))
                    await self.__mitm_mapper.set_pokestop_visits(origin,
                                                                 int(player_stats['poke_stop_visits']))
                    await cache.set(cache_key, int(time.time()), ex=60)
                    return
