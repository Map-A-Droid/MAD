import asyncio
import time
from asyncio import Task
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.data_handler.stats.PlayerStats import PlayerStats
from mapadroid.data_handler.stats.holder.AbstractStatsHolder import AbstractStatsHolder
from mapadroid.data_handler.stats.holder.stats_detect_seen.StatsDetectSeenTypeHolder import StatsDetectSeenTypeHolder
from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.helper.TrsStatsDetectHelper import TrsStatsDetectHelper
from mapadroid.db.helper.TrsStatsDetectWildMonRawHelper import TrsStatsDetectWildMonRawHelper
from mapadroid.db.helper.TrsStatsLocationHelper import TrsStatsLocationHelper
from mapadroid.db.helper.TrsStatsLocationRawHelper import TrsStatsLocationRawHelper
from mapadroid.utils.DatetimeWrapper import DatetimeWrapper
from mapadroid.utils.collections import Location
from mapadroid.utils.logging import get_logger, LoggerEnums
from mapadroid.utils.madGlobals import TransportType, PositionType, MonSeenTypes
from mapadroid.worker.WorkerType import WorkerType

logger = get_logger(LoggerEnums.mitm_mapper)


class StatsHandler:
    """
    Class to handle all kinds of stats and the submission towards DB thereof
    """

    def __init__(self, db_wrapper: DbWrapper, application_args):
        self.__application_args = application_args
        self.__db_wrapper = db_wrapper
        self.__submission_loop_task: Optional[Task] = None
        self.__stats_detect_seen_type_holder: Optional[StatsDetectSeenTypeHolder] = None
        self.__init_stats_holders()

    async def start(self):
        if not self.__submission_loop_task:
            logger.debug2("Starting stats collector")
            loop = asyncio.get_running_loop()
            self.__submission_loop_task = loop.create_task(self.__stats_submission_loop())

    async def stop(self):
        if self.__submission_loop_task:
            self.__submission_loop_task.cancel()
            self.__submission_loop_task = None

    def __init_stats_holders(self) -> None:
        self.__worker_stats: Dict[str, PlayerStats] = {}
        if self.__application_args.game_stats_mon_seen:
            self.__stats_detect_seen_type_holder: Optional[StatsDetectSeenTypeHolder] = StatsDetectSeenTypeHolder()

    def __ensure_player_stat(self, worker: str) -> PlayerStats:
        if worker not in self.__worker_stats:
            self.__worker_stats[worker] = PlayerStats(worker, self.__application_args)
        return self.__worker_stats[worker]

    def stats_collect_wild_mon(self, worker: str, encounter_ids: List[int], time_scanned: datetime) -> None:
        player_stats: PlayerStats = self.__ensure_player_stat(worker)
        for encounter_id in encounter_ids:
            player_stats.stats_collect_wild_mon(encounter_id, time_scanned)
            if self.__stats_detect_seen_type_holder:
                self.__stats_detect_seen_type_holder.add(encounter_id, MonSeenTypes.wild, time_scanned)

    def stats_collect_mon_iv(self, worker: str, encounter_id: int, time_scanned: datetime, is_shiny: bool) -> None:
        player_stats: PlayerStats = self.__ensure_player_stat(worker)
        player_stats.stats_collect_mon_iv(encounter_id, time_scanned, is_shiny)
        if self.__stats_detect_seen_type_holder:
            self.__stats_detect_seen_type_holder.add(encounter_id, MonSeenTypes.encounter, time_scanned)

    def stats_collect_quest(self, worker: str, time_scanned: datetime) -> None:
        player_stats: PlayerStats = self.__ensure_player_stat(worker)
        player_stats.stats_collect_quest(time_scanned)

    def stats_collect_raid(self, worker: str, time_scanned: datetime) -> None:
        player_stats: PlayerStats = self.__ensure_player_stat(worker)
        player_stats.stats_collect_raid(time_scanned)

    def stats_collect_location_data(self, worker: str, location: Location, success: bool, fix_timestamp: int,
                                    position_type: PositionType, data_timestamp: int, worker_type: WorkerType,
                                    transport_type: TransportType, timestamp_of_record: int) -> None:
        player_stats: PlayerStats = self.__ensure_player_stat(worker)
        player_stats.stats_collect_location_data(location, success, fix_timestamp, position_type, data_timestamp,
                                                 worker_type, transport_type, timestamp_of_record)

    def stats_collect_seen_type(self, encounter_ids: List[int], type_of_detection: MonSeenTypes,
                                time_of_scan: datetime) -> None:
        if self.__stats_detect_seen_type_holder:
            for encounter_id in encounter_ids:
                self.__stats_detect_seen_type_holder.add(encounter_id, type_of_detection, time_of_scan)

    async def __stats_submission_loop(self):
        repetition_duration: int = self.__application_args.game_stats_save_time if self.__application_args.game_stats_save_time > 15 else 300
        while True:
            await asyncio.sleep(repetition_duration)
            await self.__run_stats_processing()

    async def __run_stats_processing(self):
        logger.info("Running stats processing")
        async with self.__db_wrapper as session, session:
            try:
                await self.__process_stats(session)
                await session.commit()
            except Exception as e:
                logger.exception(e)
                await session.rollback()

    async def __process_stats(self, session: AsyncSession):
        logger.info('Submitting stats')
        submittable_stats: List[AbstractStatsHolder] = []
        if self.__stats_detect_seen_type_holder:
            submittable_stats.append(self.__stats_detect_seen_type_holder)
            self.__stats_detect_seen_type_holder = None
        submittable_stats.extend(self.__worker_stats.values())
        self.__worker_stats = None
        self.__init_stats_holders()
        for submittable in submittable_stats:
            await submittable.submit(session)

        await self.__cleanup_stats(session)
        logger.info("Done submitting stats")

    async def __cleanup_stats(self, session: AsyncSession) -> None:
        delete_before_timestamp: int = int(time.time()) - 604800
        # TODO: Cleanup seen stuff...
        await TrsStatsDetectHelper.cleanup(session, delete_before_timestamp)
        await TrsStatsDetectWildMonRawHelper.cleanup(session, DatetimeWrapper.fromtimestamp(delete_before_timestamp),
                                                     raw_delete_shiny_days=self.__application_args.raw_delete_shiny)
        await TrsStatsLocationHelper.cleanup(session, delete_before_timestamp)
        await TrsStatsLocationRawHelper.cleanup(session, delete_before_timestamp)
