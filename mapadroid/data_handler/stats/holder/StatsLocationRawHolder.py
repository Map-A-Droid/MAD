from typing import List

from mapadroid.data_handler.stats.holder.AbstractStatsHolder import AbstractStatsHolder
from mapadroid.data_handler.stats.holder.AbstractWorkerStats import AbstractWorkerStats
from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.db.model import TrsStatsLocationRaw
from mapadroid.utils.collections import Location
from mapadroid.utils.madGlobals import PositionType, TransportType


class StatsLocationRawHolder(AbstractStatsHolder, AbstractWorkerStats):
    def __init__(self, worker: str):
        AbstractWorkerStats.__init__(self, worker)
        self._entries: List[TrsStatsLocationRaw] = []

    async def submit(self, session: AsyncSession) -> None:
        async with session.begin_nested() as nested:
            session.add_all(self._entries)
            await nested.commit()
            # TODO: Catch IntegrityError/handle update

    def add_location(self, location: Location, success: bool, fix_timestamp: int,
                     position_type: PositionType, data_timestamp: int, walker: str,
                     transport_type: TransportType, timestamp_of_record: int) -> None:
        stat = TrsStatsLocationRaw()
        stat.worker = self._worker
        stat.fix_ts = fix_timestamp
        stat.lat = location.lat
        stat.lng = location.lng
        stat.data_ts = data_timestamp
        stat.type = position_type.value
        stat.walker = walker
        stat.success = 1 if success else 0
        stat.period = timestamp_of_record
        stat.transporttype = transport_type.value
        self._entries.append(stat)
