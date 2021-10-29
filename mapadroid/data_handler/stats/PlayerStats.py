from datetime import datetime
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.data_handler.stats.holder.AbstractStatsHolder import AbstractStatsHolder
from mapadroid.data_handler.stats.holder.stats_detect.StatsDetectHolder import StatsDetectHolder
from mapadroid.data_handler.stats.holder.stats_location.StatsLocationHolder import StatsLocationHolder
from mapadroid.data_handler.stats.holder.stats_location_raw.StatsLocationRawHolder import StatsLocationRawHolder
from mapadroid.data_handler.stats.holder.wild_mon_stats.WildMonStatsHolder import WildMonStatsHolder
from mapadroid.utils.collections import Location
from mapadroid.utils.logging import LoggerEnums, get_logger
from mapadroid.utils.madGlobals import PositionType, TransportType, application_args
from mapadroid.worker.WorkerType import WorkerType

logger = get_logger(LoggerEnums.stats_handler)


class PlayerStats(AbstractStatsHolder):
    def __init__(self, origin: str):
        self._worker: str = origin
        self._stats_location_raw_holder: Optional[StatsLocationRawHolder] = None
        self._wild_mon_stats_holder: Optional[WildMonStatsHolder] = None
        self.__init_holders()

    def __init_holders(self):
        self._stats_detect_holder: StatsDetectHolder = StatsDetectHolder(self._worker)
        self._stats_location_holder: StatsLocationHolder = StatsLocationHolder(self._worker)
        if application_args.game_stats_raw:
            self._wild_mon_stats_holder: WildMonStatsHolder = WildMonStatsHolder(self._worker)
            self._stats_location_raw_holder: StatsLocationRawHolder = StatsLocationRawHolder(self._worker)

    async def submit(self, session: AsyncSession) -> None:
        holders_to_submit: List[AbstractStatsHolder] = [self._stats_detect_holder, self._stats_location_holder]
        if self._wild_mon_stats_holder:
            holders_to_submit.append(self._wild_mon_stats_holder)
        if application_args.game_stats_raw:
            holders_to_submit.append(self._stats_location_raw_holder)
        del self._stats_location_holder
        del self._stats_detect_holder
        del self._wild_mon_stats_holder
        del self._stats_location_raw_holder
        self.__init_holders()

        for holder in holders_to_submit:
            async with session.begin_nested() as nested:
                try:
                    await holder.submit(session)
                    await nested.commit()
                except Exception as e:
                    await nested.rollback()
                    logger.warning("Failed submitting stats: {}", e)
        del holders_to_submit

    def stats_collect_wild_mon(self, encounter_id: int, time_scanned: datetime):
        if self._wild_mon_stats_holder:
            self._wild_mon_stats_holder.add(encounter_id, time_scanned, is_shiny=False)
        self._stats_detect_holder.add_mon(time_scanned)

    def stats_collect_mon_iv(self, encounter_id: int, time_scanned: datetime, is_shiny: bool):
        if self._wild_mon_stats_holder:
            self._wild_mon_stats_holder.add(encounter_id, time_scanned, is_shiny=is_shiny)
        self._stats_detect_holder.add_mon_iv(time_scanned)

    def stats_collect_quest(self, time_scanned: datetime):
        self._stats_detect_holder.add_quest(time_scanned)

    def stats_collect_raid(self, time_scanned: datetime, amount: int = 1):
        self._stats_detect_holder.add_raid(time_scanned, amount)

    def stats_collect_location_data(self, location: Location, success: bool, fix_timestamp: int,
                                    position_type: PositionType, data_timestamp: int, worker_type: WorkerType,
                                    transport_type: TransportType, timestamp_of_record: int):
        if self._stats_location_raw_holder:
            self._stats_location_raw_holder.add_location(location, success, fix_timestamp, position_type,
                                                         data_timestamp, worker_type, transport_type,
                                                         timestamp_of_record)
        if success:
            self._stats_location_holder.add_location_ok(timestamp_of_record)
        else:
            self._stats_location_holder.add_location_not_ok(timestamp_of_record)
