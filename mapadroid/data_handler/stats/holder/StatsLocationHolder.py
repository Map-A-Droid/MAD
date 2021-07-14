from datetime import datetime

from mapadroid.data_handler.stats.holder.AbstractStatsHolder import AbstractStatsHolder
from mapadroid.data_handler.stats.holder.AbstractWorkerStats import AbstractWorkerStats
from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.db.model import TrsStatsLocation


class StatsLocationEntry(TrsStatsLocation):
    def __init__(self, worker: str):
        super().__init__()
        self.worker = worker
        self.timestamp_scan = datetime.utcnow()
        self.location_ok = 0
        self.location_nok = 0

    def update(self, time_of_scan: datetime, location_ok: bool):
        self.timestamp_scan = time_of_scan
        if location_ok:
            self.location_ok += 1
        else:
            self.location_nok += 1


class StatsLocationHolder(AbstractStatsHolder, AbstractWorkerStats):
    def __init__(self, worker: str):
        AbstractWorkerStats.__init__(self, worker)
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
