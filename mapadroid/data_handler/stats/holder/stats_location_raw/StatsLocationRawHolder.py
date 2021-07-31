from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.data_handler.AbstractWorkerHolder import AbstractWorkerHolder
from mapadroid.data_handler.stats.holder.AbstractStatsHolder import AbstractStatsHolder
from mapadroid.db.model import TrsStatsLocationRaw
from mapadroid.utils.collections import Location
from mapadroid.utils.madGlobals import PositionType, TransportType
from loguru import logger


class StatsLocationRawHolder(AbstractStatsHolder, AbstractWorkerHolder):
    def __init__(self, worker: str):
        AbstractWorkerHolder.__init__(self, worker)
        self._entries: List[TrsStatsLocationRaw] = []

    async def submit(self, session: AsyncSession) -> None:
        for entry in self._entries:
            async with session.begin_nested() as nested:
                try:
                    session.add(entry)
                    await nested.commit()
                except Exception as e:
                    logger.info("Failed submitting raw location stats: {}", e)
                    await nested.rollback()
        del self._entries

    def add_location(self, location: Location, success: bool, fix_timestamp: int,
                     position_type: PositionType, data_timestamp: int, walker: str,
                     transport_type: TransportType, timestamp_of_record: int) -> None:
        stat = TrsStatsLocationRaw()
        stat.worker = self._worker
        stat.fix_ts = fix_timestamp
        stat.lat = location.lat
        stat.lng = location.lng
        stat.data_ts = data_timestamp
        stat.type = position_type.value if position_type else PositionType.STARTUP.value
        stat.walker = walker
        stat.success = 1 if success else 0
        stat.period = timestamp_of_record
        stat.transporttype = transport_type.value if transport_type else TransportType.TELEPORT.value
        self._entries.append(stat)
