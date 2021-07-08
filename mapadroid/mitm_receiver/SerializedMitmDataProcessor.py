import asyncio
import time
from datetime import datetime
from typing import List, Tuple, Optional

import sqlalchemy
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.db.DbPogoProtoSubmit import DbPogoProtoSubmit
from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.mitm_receiver.MitmMapper import MitmMapper
from mapadroid.utils.madGlobals import MitmReceiverRetry


class SerializedMitmDataProcessor:
    def __init__(self, data_queue: asyncio.Queue, application_args, mitm_mapper: MitmMapper,
                 db_wrapper: DbWrapper, name=None):
        self.__queue: asyncio.Queue = data_queue
        self.__db_wrapper: DbWrapper = db_wrapper
        # TODO: Init DbPogoProtoSubmit per processing passing session to constructor
        self.__db_submit: DbPogoProtoSubmit = db_wrapper.proto_submit
        self.__application_args = application_args
        self.__mitm_mapper: MitmMapper = mitm_mapper
        self.__name = name

    async def run(self):
        logger.info("Starting serialized MITM data processor")
        # TODO: use event to stop... Remove try/catch...
        with logger.contextualize(name=self.__name):
            while True:
                try:
                    item = await self.__queue.get()
                    if item is None:
                        logger.info("Received signal to stop MITM data processor")
                        break
                    start_time = self.get_time_ms()
                    async with self.__db_wrapper as session, session:
                        async with session.begin() as transaction:
                            try:
                                await self.process_data(session, received_timestamp=item[0], data=item[1],
                                                        origin=item[2])
                                await session.commit()
                            except (sqlalchemy.exc.IntegrityError, MitmReceiverRetry) as e:
                                logger.info("Failed submitting data to DB, rescheduling. {}", e)
                                await transaction.rollback()
                                await self.__queue.put(item)
                            except Exception as e:
                                logger.warning("Failed processing data... {}", e)
                                logger.exception(e)
                                await transaction.rollback()
                                await self.__queue.put(item)
                    self.__queue.task_done()
                    end_time = self.get_time_ms() - start_time
                    logger.debug("MITM data processor {} finished queue item in {}ms", self.__name, end_time)
                except KeyboardInterrupt:
                    logger.info("Received keyboard interrupt, stopping MITM data processor")

    # @logger.catch
    async def process_data(self, session: AsyncSession, received_timestamp, data, origin):
        data_type = data.get("type", None)
        logger.debug("Processing received data")
        processed_timestamp = datetime.fromtimestamp(received_timestamp)

        if data_type and not data.get("raw", False):
            await self.__mitm_mapper.run_stats_collector(origin)

            logger.debug4("Received data: {}", data)
            threshold_seconds = self.__application_args.mitm_ignore_proc_time_thresh

            start_time = self.get_time_ms()
            if threshold_seconds > 0:
                minimum_timestamp = (start_time / 1000) - threshold_seconds
                if received_timestamp < minimum_timestamp:
                    logger.debug(
                        "Data received at {} is older than configured threshold of {}s ({}). Ignoring data.",
                        processed_timestamp, threshold_seconds, datetime.fromtimestamp(minimum_timestamp))
                    return

            # We can use the current session easily...
            if data_type == 106:
                logger.info("Processing GMO. Received at {}", processed_timestamp)
                weather_time = await self.__process_weather(data, origin, received_timestamp, session)
                stops_time = await self.__process_stops(data, origin, session)
                gyms_time = await self.__process_gyms(data, origin, session)
                raids_time = await self.__process_raids(data, origin, session)
                spawnpoints_time = await self.__process_spawnpoints(data, origin, processed_timestamp, session)
                cells_time = await self.__process_cells(data, origin, session)

                gmo_loc_start = self.get_time_ms()
                self.__mitm_mapper.submit_gmo_for_location(origin, data["payload"])
                gmo_loc_time = self.get_time_ms() - gmo_loc_start

                lure_wild: List[Tuple[int, datetime]] = []
                if self.__application_args.scan_lured_mons:
                    lurenoiv_start = self.get_time_ms()
                    lure_wild = await self.__db_submit.mon_lure_noiv(session, origin, received_timestamp,
                                                                     data["payload"],
                                                                     self.__mitm_mapper)
                    lurenoiv_time = self.get_time_ms() - lurenoiv_start
                else:
                    lurenoiv_time = 0

                if self.__application_args.scan_nearby_mons:
                    nearby_mons_time_start = self.get_time_ms()
                    try:
                        cell_encounters, stop_encounters = await self.__db_submit.mons_nearby(session,
                                                                                              origin, received_timestamp,
                                                                                              data["payload"],
                                                                                              self.__mitm_mapper)
                    except Exception as e:
                        logger.exception(e)
                    nearby_mons_time = self.get_time_ms() - nearby_mons_time_start
                else:
                    cell_encounters = []
                    stop_encounters = []
                    nearby_mons_time = 0

                mons_time, wild_encounter_ids_processed = await self.__process_wild_mons(data, origin,
                                                                                         received_timestamp,
                                                                                         session)
                if self.__application_args.game_stats:
                    await self.__db_submit.update_seen_type_stats(session,
                                                                  wild=wild_encounter_ids_processed,
                                                                  lure_wild=lure_wild,
                                                                  nearby_cell=cell_encounters,
                                                                  nearby_stop=stop_encounters
                                                                  )

                full_time = self.get_time_ms() - start_time

                logger.debug("Done processing GMO in {}ms (weather={}ms, stops={}ms, gyms={}ms, raids={}ms, " +
                             "spawnpoints={}ms, mons={}ms, "
                             "nearby_mons={}, lure_noiv={}, cells={}ms, "
                             "gmo_loc={}ms)",
                             full_time, weather_time, stops_time, gyms_time, raids_time,
                             spawnpoints_time, mons_time, nearby_mons_time, lurenoiv_time,
                             cells_time, gmo_loc_time)
            elif data_type == 102:
                playerlevel = await self.__mitm_mapper.get_playerlevel(origin)
                if playerlevel >= 30:
                    logger.debug("Processing encounter received at {}", processed_timestamp)
                    encounter: Optional[Tuple[int, datetime]] = await self.__db_submit.mon_iv(session, origin,
                                                                                              received_timestamp,
                                                                                              data["payload"],
                                                                                              self.__mitm_mapper)

                    if self.__application_args.game_stats and encounter:
                        await self.__db_submit.update_seen_type_stats(session, encounter=encounter)
                    end_time = self.get_time_ms() - start_time
                    logger.debug("Done processing encounter in {}ms", end_time)
                else:
                    logger.warning("Playerlevel lower than 30 - not processing encounter IVs")
            elif data_type == 145:
                # lure mons with iv
                playerlevel = await self.__mitm_mapper.get_playerlevel(origin)
                if self.__application_args.scan_lured_mons and (playerlevel >= 30):
                    logger.debug("Processing lure encounter received at {}", processed_timestamp)

                    lure_encounter: Optional[Tuple[int, datetime]] = await self.__db_submit \
                        .mon_lure_iv(session, origin, received_timestamp, data["payload"], self.__mitm_mapper)

                    if self.__application_args.game_stats:
                        await self.__db_submit.update_seen_type_stats(session, lure_encounter=lure_encounter)

                    end_time = self.get_time_ms() - start_time
                    logger.debug("Done processing lure encounter in {}ms", end_time)
            elif data_type == 101:
                logger.debug("Processing proto 101 (FORT_SEARCH)")
                await self.__db_submit.quest(session, origin, data["payload"], self.__mitm_mapper)
                end_time = self.get_time_ms() - start_time
                logger.debug("Done processing proto 101 in {}ms", end_time)
            elif data_type == 104:
                logger.debug("Processing proto 104 (FORT_DETAILS)")
                await self.__db_submit.stop_details(session, data["payload"])
                end_time = self.get_time_ms() - start_time
                logger.debug("Done processing proto 104 in {}ms", end_time)
            elif data_type == 4:
                logger.debug("Processing proto 4 (GET_HOLO_INVENTORY)")
                await self.__mitm_mapper.generate_player_stats(origin, data["payload"])
                end_time = self.get_time_ms() - start_time
                logger.debug("Done processing proto 4 in {}ms", end_time)
            elif data_type == 156:
                logger.debug("Processing proto 156 (GYM_GET_INFO)")
                await self.__db_submit.gym(session, origin, data["payload"])
                end_time = self.get_time_ms() - start_time
                logger.debug("Done processing proto 156 in {}ms", end_time)

    async def __process_wild_mons(self, data, origin, received_timestamp, session):
        mons_time_start = self.get_time_ms()
        encounter_ids_processed: List[Tuple[int, datetime]] = await self.__db_submit.mons(session, origin,
                                                                                          received_timestamp,
                                                                                          data["payload"],
                                                                                          self.__mitm_mapper)

        mons_time = self.get_time_ms() - mons_time_start
        return mons_time, encounter_ids_processed

    async def __process_cells(self, data, origin, session):
        cells_time_start = self.get_time_ms()
        await self.__db_submit.cells(session, origin, data["payload"])
        cells_time = self.get_time_ms() - cells_time_start
        return cells_time

    async def __process_spawnpoints(self, data, origin, processed_timestamp, session):
        spawnpoints_time_start = self.get_time_ms()
        await self.__db_submit.spawnpoints(session, origin, data["payload"], processed_timestamp)
        spawnpoints_time = self.get_time_ms() - spawnpoints_time_start
        return spawnpoints_time

    async def __process_raids(self, data, origin, session):
        raids_time_start = self.get_time_ms()
        await self.__db_submit.raids(session, origin, data["payload"], self.__mitm_mapper)
        raids_time = self.get_time_ms() - raids_time_start
        return raids_time

    async def __process_gyms(self, data, origin, session):
        gyms_time_start = self.get_time_ms()
        # TODO: If return value False, rollback transaction?
        await self.__db_submit.gyms(session, origin, data["payload"])
        gyms_time = self.get_time_ms() - gyms_time_start
        return gyms_time

    async def __process_stops(self, data, origin, session):
        stops_time_start = self.get_time_ms()
        # TODO: If return value False, rollback transaction?
        await self.__db_submit.stops(session, origin, data["payload"])
        stops_time = self.get_time_ms() - stops_time_start
        return stops_time

    async def __process_weather(self, data, origin, received_timestamp, session):
        weather_time_start = self.get_time_ms()
        await self.__db_submit.weather(session, origin, data["payload"], received_timestamp)
        weather_time = self.get_time_ms() - weather_time_start
        return weather_time

    @staticmethod
    def get_time_ms():
        return int(time.time() * 1000)
