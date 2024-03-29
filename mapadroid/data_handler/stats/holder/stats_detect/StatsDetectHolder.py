import time
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.data_handler.AbstractWorkerHolder import AbstractWorkerHolder
from mapadroid.data_handler.stats.holder.AbstractStatsHolder import AbstractStatsHolder
from mapadroid.data_handler.stats.holder.stats_detect.StatsDetectEntry import StatsDetectEntry


class StatsDetectHolder(AbstractStatsHolder, AbstractWorkerHolder):
    def __init__(self, worker: str):
        # Wild mon encounterID to counts seen mapping
        AbstractWorkerHolder.__init__(self, worker)
        self._entry: StatsDetectEntry = StatsDetectEntry(worker)

    async def submit(self, session: AsyncSession) -> None:
        self._entry.timestamp_scan = int(time.time())
        async with session.begin_nested() as nested:
            session.add(self._entry)
            await nested.commit()
        del self._entry

    def add_mon(self, time_scanned: datetime) -> None:
        self._entry.update(time_scanned, new_mons=1)

    def add_raid(self, time_scanned: datetime, amount: int = 1) -> None:
        self._entry.update(time_scanned, new_raids=amount)

    def add_mon_iv(self, time_scanned: datetime) -> None:
        self._entry.update(time_scanned, new_mon_ivs=1)

    def add_quest(self, time_scanned: datetime) -> None:
        self._entry.update(time_scanned, new_quests=1)
