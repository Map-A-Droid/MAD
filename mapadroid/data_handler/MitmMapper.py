import asyncio
import time
from queue import Empty
from typing import Dict, Optional, Tuple, List

from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.helper.TrsStatsDetectFortRawHelper import TrsStatsDetectFortRawHelper
from mapadroid.db.helper.TrsStatsDetectHelper import TrsStatsDetectHelper
from mapadroid.db.helper.TrsStatsDetectMonRawHelper import TrsStatsDetectMonRawHelper
from mapadroid.db.helper.TrsStatsLocationHelper import TrsStatsLocationHelper
from mapadroid.db.helper.TrsStatsLocationRawHelper import TrsStatsLocationRawHelper
from mapadroid.mapping_manager.MappingManager import MappingManager, DeviceMappingsEntry
from mapadroid.data_handler.stats.PlayerStats import PlayerStats
from mapadroid.utils.collections import Location
from loguru import logger


class MitmMapper(object):
    def __init__(self, args, mapping_manager: MappingManager, db_wrapper: DbWrapper):
        self.__mapping = {}
        self.__playerstats: Dict[str, PlayerStats] = {}
        self.__mapping_manager: MappingManager = mapping_manager
        self.__injected = {}
        self.__last_cellsid = {}
        self.__last_possibly_moved = {}
        self.__application_args = args
        self.__db_wrapper: DbWrapper = db_wrapper
        self.__playerstats_db_update_stop: asyncio.Event = asyncio.Event()
        self.__playerstats_db_update_queue: asyncio.Queue = asyncio.Queue()
        self.__playerstats_db_update_consumer = None

    async def init(self):
        loop = asyncio.get_event_loop()
        self.__playerstats_db_update_consumer = loop.create_task(self.__internal_playerstats_db_update_consumer())
        if self.__mapping_manager is not None:
            devicemappings: Optional[
                Dict[str, DeviceMappingsEntry]] = await self.__mapping_manager.get_all_devicemappings()
            for origin in devicemappings.keys():
                await self.__add_new_device(origin)

    async def __add_new_device(self, origin: str) -> None:
        self.__mapping[origin] = {}
        self.__playerstats[origin] = PlayerStats(origin, self.__application_args, self)

    async def add_stats_to_process(self, client_id, stats, last_processed_timestamp):
        if self.__application_args.game_stats:
            await self.__playerstats_db_update_queue.put((client_id, stats, last_processed_timestamp))

    async def __internal_playerstats_db_update_consumer(self):
        try:
            while not self.__playerstats_db_update_stop.is_set():
                if not self.__application_args.game_stats:
                    logger.info("Playerstats are disabled")
                    break
                try:
                    next_item = self.__playerstats_db_update_queue.get_nowait()
                except Empty:
                    await asyncio.sleep(0.5)
                    continue
                if next_item is not None:
                    client_id, stats, last_processed_timestamp = next_item
                    # TODO: Place data in dict accordingly
        except Exception as e:
            logger.error("Playerstats consumer stopping because of {}", e)
        logger.info("Shutting down Playerstats update consumer")

    def shutdown(self):
        self.__playerstats_db_update_stop.set()
        self.__playerstats_db_update_consumer.cancel()

    # TODO: Move to MappingManager?
    async def set_injection_status(self, origin, status=True):
        if origin not in self.__injected or not self.__injected[origin] and status is True:
            logger.success("Worker is injected now")
        self.__injected[origin] = status

    async def get_injection_status(self, origin):
        return self.__injected.get(origin, False)

    async def run_stats_collector(self, origin: str):
        if not self.__application_args.game_stats:
            pass

        logger.debug2("Running stats collector")
        if self.__playerstats.get(origin, None) is not None:
            await self.__playerstats.get(origin).stats_collector()

    async def collect_location_stats(self, origin: str, location: Location, datarec, start_timestamp: float,
                                     positiontype,
                                     rec_timestamp: float, walker, transporttype):
        if self.__playerstats.get(origin, None) is not None and location is not None:
            await self.__playerstats.get(origin).stats_collect_location_data(location, datarec, start_timestamp,
                                                                             positiontype,
                                                                             rec_timestamp, walker, transporttype)

    # TODO: Move to TrsStatus DB entry
    async def get_playerlevel(self, origin: str):
        if self.__playerstats.get(origin, None) is not None:
            return self.__playerstats.get(origin).get_level()
        else:
            return -1

    async def get_poke_stop_visits(self, origin: str) -> int:
        if self.__playerstats.get(origin, None) is not None:
            return self.__playerstats.get(origin).get_poke_stop_visits()
        else:
            return -1

    async def collect_mon_stats(self, origin: str, encounter_id: str):
        if self.__playerstats.get(origin, None) is not None:
            await self.__playerstats.get(origin).stats_collect_mon(encounter_id)

    async def collect_mon_iv_stats(self, origin: str, encounter_id: str, shiny: int):
        if self.__playerstats.get(origin, None) is not None:
            await self.__playerstats.get(origin).stats_collect_mon_iv(encounter_id, shiny)

    async def collect_quest_stats(self, origin: str, stop_id: str):
        if self.__playerstats.get(origin, None) is not None:
            await self.__playerstats.get(origin).stats_collect_quest(stop_id)

    async def generate_player_stats(self, origin: str, inventory_proto: dict):
        if self.__playerstats.get(origin, None) is not None:
            await self.__playerstats.get(origin).gen_player_stats(inventory_proto)
