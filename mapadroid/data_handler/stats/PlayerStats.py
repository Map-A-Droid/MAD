from datetime import datetime
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.data_handler.stats.holder.AbstractStatsHolder import AbstractStatsHolder
from mapadroid.data_handler.stats.holder.StatsDetectHolder import StatsDetectHolder
from mapadroid.data_handler.stats.holder.StatsLocationHolder import StatsLocationHolder
from mapadroid.data_handler.stats.holder.StatsLocationRawHolder import StatsLocationRawHolder
from mapadroid.data_handler.stats.holder.WildMonStatsHolder import WildMonStatsHolder
from mapadroid.utils.collections import Location
from mapadroid.utils.madGlobals import PositionType, TransportType


class PlayerStats(AbstractStatsHolder):
    def __init__(self, origin: str, application_args):
        self._worker: str = origin
        self.__application_args = application_args

        self.__init_holders()

    def __init_holders(self):
        self._stats_detect_holder: StatsDetectHolder = StatsDetectHolder(self._worker)
        self._stats_location_holder: StatsLocationHolder = StatsLocationHolder(self._worker)
        self._wild_mon_stats_holder: WildMonStatsHolder = WildMonStatsHolder(self._worker)
        self._stats_location_raw_holder: StatsLocationRawHolder = StatsLocationRawHolder(self._worker)

    async def submit(self, session: AsyncSession) -> None:
        holders_to_submit: List[AbstractStatsHolder] = [self._stats_detect_holder, self._stats_location_holder,
                                                        self._wild_mon_stats_holder, self._stats_location_raw_holder]
        self.__init_holders()

        for holder in holders_to_submit:
            await holder.submit(session)

    def stats_collect_wild_mon(self, encounter_id: int, time_scanned: datetime):
        self._wild_mon_stats_holder.add(encounter_id, time_scanned, is_shiny=False)
        self._stats_detect_holder.add_mon(time_scanned)

    def stats_collect_mon_iv(self, encounter_id: int, time_scanned: datetime, is_shiny: bool):
        self._wild_mon_stats_holder.add(encounter_id, time_scanned, is_shiny=is_shiny)
        self._stats_detect_holder.add_mon_iv(time_scanned)

    def stats_collect_quest(self, time_scanned: datetime):
        self._stats_detect_holder.add_quest(time_scanned)

    def stats_collect_raid(self, time_scanned: datetime):
        self._stats_detect_holder.add_raid(time_scanned)

    def stats_collect_location_data(self, location: Location, success: bool, fix_timestamp: int,
                                          position_type: PositionType, data_timestamp: int, walker: str,
                                          transport_type: TransportType, timestamp_of_record: int):
        self._stats_location_raw_holder.add_location(location, success, fix_timestamp, position_type,
                                                     data_timestamp, walker, transport_type, timestamp_of_record)
        if data_timestamp > 0:
            self._stats_location_holder.add_location_ok(datetime.utcfromtimestamp(timestamp_of_record))
        else:
            self._stats_location_holder.add_location_not_ok(datetime.utcfromtimestamp(timestamp_of_record))
