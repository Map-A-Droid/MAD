from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.data_handler.AbstractWorkerHolder import AbstractWorkerHolder
from mapadroid.data_handler.stats.holder.AbstractStatsHolder import AbstractStatsHolder
from mapadroid.data_handler.stats.holder.stats_location.StatsLocationEntry import StatsLocationEntry
from mapadroid.utils.logging import get_logger, LoggerEnums

logger = get_logger(LoggerEnums.mitm_mapper)


class StatsLocationHolder(AbstractStatsHolder, AbstractWorkerHolder):
    def __init__(self, worker: str):
        AbstractWorkerHolder.__init__(self, worker)
        self._entry: StatsLocationEntry = StatsLocationEntry(worker)

    async def submit(self, session: AsyncSession) -> None:
        async with session.begin_nested() as nested:
            try:
                session.add(self._entry)
                await nested.commit()
            except Exception as e:
                logger.warning("Failed submitting location data of {}", self._worker)
        del self._entry

    def add_location_ok(self, time_of_scan: int) -> None:
        self._entry.update(time_of_scan, location_ok=True)

    def add_location_not_ok(self, time_of_scan: int) -> None:
        self._entry.update(time_of_scan, location_ok=False)
