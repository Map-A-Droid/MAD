from datetime import datetime
from typing import List

from grpc.aio import AioRpcError
from loguru import logger

from mapadroid.data_handler.stats.AbstractStatsHandler import AbstractStatsHandler
from mapadroid.grpc.compiled.stats_handler.stats_handler_pb2 import Stats
from mapadroid.grpc.stubs.stats_handler.stats_handler_pb2_grpc import StatsHandlerStub
from mapadroid.utils.collections import Location
from mapadroid.utils.madGlobals import MonSeenTypes, PositionType, TransportType
from mapadroid.worker.WorkerType import WorkerType


class StatsHandlerClient(StatsHandlerStub, AbstractStatsHandler):
    def __init__(self, channel):
        super().__init__(channel)

    async def stats_collect_wild_mon(self, worker: str, encounter_ids: List[int], time_scanned: datetime) -> None:
        request: Stats = Stats()
        request.worker.name = worker
        request.timestamp = int(time_scanned.timestamp())
        request.wild_mons.encounter_ids.extend(encounter_ids)
        try:
            await self.StatsCollect(request)
        except AioRpcError as e:
            logger.warning("Failed submitting wild mon stats {}", e)

    async def stats_collect_mon_iv(self, worker: str, encounter_id: int, time_scanned: datetime,
                                   is_shiny: bool) -> None:
        request: Stats = Stats()
        request.worker.name = worker
        request.timestamp = int(time_scanned.timestamp())
        request.mon_iv.encounter_id = encounter_id
        request.mon_iv.is_shiny = is_shiny
        try:
            await self.StatsCollect(request)
        except AioRpcError as e:
            logger.warning("Failed submitting mon IV stats {}", e)

    async def stats_collect_quest(self, worker: str, time_scanned: datetime) -> None:
        request: Stats = Stats()
        request.worker.name = worker
        request.timestamp = int(time_scanned.timestamp())
        request.quest.SetInParent()
        try:
            await self.StatsCollect(request)
        except AioRpcError as e:
            logger.warning("Failed submitting quest stats {}", e)

    async def stats_collect_raid(self, worker: str, time_scanned: datetime, amount: int = 1) -> None:
        request: Stats = Stats()
        request.worker.name = worker
        request.timestamp = int(time_scanned.timestamp())
        request.raid.amount = amount
        try:
            await self.StatsCollect(request)
        except AioRpcError as e:
            logger.warning("Failed submitting raid stats {}", e)

    async def stats_collect_location_data(self, worker: str, location: Location, success: bool, fix_timestamp: int,
                                          position_type: PositionType, data_timestamp: int, walker: WorkerType,
                                          transport_type: TransportType, timestamp_of_record: int) -> None:
        request: Stats = Stats()
        request.worker.name = worker
        request.timestamp = timestamp_of_record
        request.location_data.location.latitude = location.lat
        request.location_data.location.longitude = location.lng
        request.location_data.success = success
        request.location_data.fix_timestamp = fix_timestamp
        request.location_data.data_timestamp = data_timestamp
        request.location_data.walker = walker.value
        # TODO: Probably gotta set it some other way...
        request.location_data.position_type = position_type.value
        request.location_data.transport_type = transport_type.value
        try:
            await self.StatsCollect(request)
        except AioRpcError as e:
            logger.warning("Failed submitting location data {}", e)

    async def stats_collect_seen_type(self, encounter_ids: List[int], type_of_detection: MonSeenTypes,
                                      time_of_scan: datetime) -> None:
        request: Stats = Stats()
        request.timestamp = int(time_of_scan.timestamp())
        request.seen_type.encounter_ids.extend(encounter_ids)
        # TODO: Probably gotta set it some other way...
        request.seen_type.type_of_detection = type_of_detection.value
        try:
            await self.StatsCollect(request)
        except AioRpcError as e:
            logger.warning("Failed submitting seen type stats {}", e)
