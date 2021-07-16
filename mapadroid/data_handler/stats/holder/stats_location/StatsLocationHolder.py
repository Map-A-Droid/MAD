from datetime import datetime

from mapadroid.data_handler.stats.holder.AbstractStatsHolder import AbstractStatsHolder
from mapadroid.data_handler.AbstractWorkerHolder import AbstractWorkerHolder
from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.data_handler.stats.holder.stats_location.StatsLocationEntry import StatsLocationEntry


class StatsLocationHolder(AbstractStatsHolder, AbstractWorkerHolder):
    def __init__(self, worker: str):
        AbstractWorkerHolder.__init__(self, worker)
        self._entry: StatsLocationEntry = StatsLocationEntry(worker)

    async def submit(self, session: AsyncSession) -> None:
        async with session.begin_nested() as nested:
            session.add(self._entry)
            await nested.commit()
            # TODO: Catch IntegrityError/handle update

    def add_location_ok(self, time_of_scan: datetime) -> None:
        self._entry.update(time_of_scan, location_ok=True)

    def add_location_not_ok(self, time_of_scan: datetime) -> None:
        self._entry.update(time_of_scan, location_ok=False)
