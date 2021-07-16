from datetime import datetime
from typing import Optional, List, Any

from mapadroid.data_handler.mitm_data.MitmDataHandler import MitmDataHandler
from mapadroid.data_handler.mitm_data.holder.latest_mitm_data.LatestMitmDataEntry import LatestMitmDataEntry
from mapadroid.data_handler.stats.StatsHandler import StatsHandler
from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.mapping_manager.MappingManager import MappingManager
from mapadroid.utils.collections import Location
from loguru import logger

from mapadroid.utils.madGlobals import PositionType, TransportType, MonSeenTypes


class MitmMapper(object):
    def __init__(self, args, mapping_manager: MappingManager, db_wrapper: DbWrapper):
        self.__mapping_manager: MappingManager = mapping_manager
        self.__application_args = args
        self.__db_wrapper: DbWrapper = db_wrapper
        self.__init_handlers()

    def __init_handlers(self):
        if self.__application_args.game_stats:
            self.__stats_handler: Optional[StatsHandler] = StatsHandler(self.__db_wrapper, self.__application_args)
        else:
            self.__stats_handler: Optional[StatsHandler] = None
        self.__mitm_data_handler: MitmDataHandler = MitmDataHandler(self.__db_wrapper, self.__application_args)

    async def start(self):
        if self.__stats_handler:
            await self.__stats_handler.start()

    async def shutdown(self):
        if self.__stats_handler:
            await self.__stats_handler.stop()

    # ##
    # Stats related methods
    # ##
    async def stats_collect_wild_mon(self, worker: str, encounter_ids: List[int], time_scanned: datetime) -> None:
        if self.__stats_handler:
            self.__stats_handler.stats_collect_wild_mon(worker, encounter_ids, time_scanned)

    async def stats_collect_mon_iv(self, worker: str, encounter_id: int, time_scanned: datetime,
                                   is_shiny: bool) -> None:
        if self.__stats_handler:
            self.__stats_handler.stats_collect_mon_iv(worker, encounter_id, time_scanned, is_shiny)

    async def stats_collect_quest(self, worker: str, stop_id: str, time_scanned: datetime) -> None:
        if self.__stats_handler:
            self.__stats_handler.stats_collect_quest(worker, time_scanned)

    async def stats_collect_raid(self, worker: str, fort_id: str, time_scanned: datetime) -> None:
        if self.__stats_handler:
            self.__stats_handler.stats_collect_raid(worker, time_scanned)

    async def stats_collect_location_data(self, worker: str, location: Location, success: bool, fix_timestamp: int,
                                            position_type: PositionType, data_timestamp: int, walker: str,
                                            transport_type: TransportType, timestamp_of_record: int) -> None:
        if self.__stats_handler:
            self.__stats_handler.stats_collect_location_data(worker, location, success, fix_timestamp, position_type,
                                                             data_timestamp, walker,
                                                             transport_type, timestamp_of_record)

    async def stats_collect_seen_type(self, encounter_ids: List[int], type_of_detection: MonSeenTypes,
                                time_of_scan: datetime) -> None:
        if self.__stats_handler:
            self.__stats_handler.stats_collect_seen_type(encounter_ids, type_of_detection, time_of_scan)

    # ##
    # Data related methods
    # ##
    async def get_last_possibly_moved(self, worker: str) -> int:
        return await self.__mitm_data_handler.get_last_possibly_moved(worker)

    async def update_latest(self, worker: str, key: str, value: Any, timestamp_received_raw: float = None,
                            timestamp_received_receiver: float = None, location: Location = None) -> None:
        self.__mitm_data_handler.update_latest(worker, key, value, timestamp_received_raw,
                                               timestamp_received_receiver, location)

    async def request_latest(self, worker: str, key: str) -> Optional[LatestMitmDataEntry]:
        return self.__mitm_data_handler.request_latest(worker, key)

    async def handle_inventory_data(self, worker: str, inventory_proto: dict) -> None:
        await self.__mitm_data_handler.handle_inventory_data(worker, inventory_proto)

    async def get_poke_stop_visits(self, worker: str) -> int:
        return await self.__mitm_data_handler.get_poke_stop_visits(worker)

    async def get_level(self, worker: str) -> int:
        return await self.__mitm_data_handler.get_level(worker)

    async def get_injection_status(self, worker: str) -> bool:
        return await self.__mitm_data_handler.get_injection_status(worker)

    async def set_injection_status(self, worker: str, status: bool) -> None:
        await self.__mitm_data_handler.set_injection_status(worker, status)
