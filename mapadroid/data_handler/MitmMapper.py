import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Union

from mapadroid.data_handler.AbstractMitmMapper import AbstractMitmMapper
from mapadroid.data_handler.mitm_data.MitmDataHandler import MitmDataHandler
from mapadroid.data_handler.mitm_data.holder.latest_mitm_data.LatestMitmDataEntry import LatestMitmDataEntry
from mapadroid.data_handler.stats.StatsHandler import StatsHandler
from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.utils.collections import Location
from mapadroid.utils.madGlobals import PositionType, TransportType, MonSeenTypes, application_args
from mapadroid.worker.WorkerType import WorkerType


class MitmMapper(AbstractMitmMapper):
    def __init__(self, db_wrapper: DbWrapper):
        self.__db_wrapper: DbWrapper = db_wrapper
        self.__init_handlers()

    def __init_handlers(self):
        if application_args.game_stats:
            self.__stats_handler: Optional[StatsHandler] = StatsHandler(self.__db_wrapper, application_args)
        else:
            self.__stats_handler: Optional[StatsHandler] = None
        self.__mitm_data_handler: MitmDataHandler = MitmDataHandler(self.__db_wrapper, application_args)

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
            loop = asyncio.get_running_loop()
            loop.run_in_executor(None, self.__stats_handler.stats_collect_wild_mon,
                                 worker, encounter_ids, time_scanned)

    async def stats_collect_mon_iv(self, worker: str, encounter_id: int, time_scanned: datetime,
                                   is_shiny: bool) -> None:
        if self.__stats_handler:
            self.__stats_handler.stats_collect_mon_iv(worker, encounter_id, time_scanned, is_shiny)

    async def stats_collect_quest(self, worker: str, time_scanned: datetime) -> None:
        if self.__stats_handler:
            self.__stats_handler.stats_collect_quest(worker, time_scanned)

    async def stats_collect_raid(self, worker: str, time_scanned: datetime) -> None:
        if self.__stats_handler:
            self.__stats_handler.stats_collect_raid(worker, time_scanned)

    async def stats_collect_location_data(self, worker: str, location: Location, success: bool, fix_timestamp: int,
                                          position_type: PositionType, data_timestamp: int, worker_type: WorkerType,
                                          transport_type: TransportType, timestamp_of_record: int) -> None:
        if self.__stats_handler:
            self.__stats_handler.stats_collect_location_data(worker, location, success, fix_timestamp, position_type,
                                                             data_timestamp, worker_type,
                                                             transport_type, timestamp_of_record)

    async def stats_collect_seen_type(self, encounter_ids: List[int], type_of_detection: MonSeenTypes,
                                      time_of_scan: datetime) -> None:
        if self.__stats_handler:
            loop = asyncio.get_running_loop()
            loop.run_in_executor(None, self.__stats_handler.stats_collect_seen_type,
                                 encounter_ids, type_of_detection, time_of_scan)

    # ##
    # Data related methods
    # ##
    async def get_last_possibly_moved(self, worker: str) -> int:
        return await self.__mitm_data_handler.get_last_possibly_moved(worker)

    async def update_latest(self, worker: str, key: str, value: Union[list, dict], timestamp_received_raw: float = None,
                            timestamp_received_receiver: float = None, location: Location = None) -> None:
        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, self.__mitm_data_handler.update_latest, worker, key, value, timestamp_received_raw,
                             timestamp_received_receiver, location)

    async def request_latest(self, worker: str, key: str,
                             timestamp_earliest: Optional[int] = None) -> Optional[LatestMitmDataEntry]:
        return self.__mitm_data_handler.request_latest(worker, key, timestamp_earliest)

    async def get_full_latest_data(self, worker: str) -> Dict[str, LatestMitmDataEntry]:
        return self.__mitm_data_handler.get_full_latest_data(worker)

    async def get_poke_stop_visits(self, worker: str) -> int:
        return await self.__mitm_data_handler.get_poke_stop_visits(worker)

    async def get_level(self, worker: str) -> int:
        return await self.__mitm_data_handler.get_level(worker)

    async def get_injection_status(self, worker: str) -> bool:
        return await self.__mitm_data_handler.get_injection_status(worker)

    async def set_injection_status(self, worker: str, status: bool) -> None:
        await self.__mitm_data_handler.set_injection_status(worker, status)

    async def get_last_known_location(self, worker: str) -> Optional[Location]:
        return self.__mitm_data_handler.get_last_known_location(worker)

    async def set_level(self, worker: str, level: int) -> None:
        await self.__mitm_data_handler.set_level(worker, level)

    async def set_pokestop_visits(self, worker: str, pokestop_visits: int) -> None:
        await self.__mitm_data_handler.set_pokestop_visits(worker, pokestop_visits)

