from datetime import datetime
from typing import Dict

from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.data_handler.stats.holder.AbstractStatsHolder import AbstractStatsHolder
from mapadroid.data_handler.AbstractWorkerHolder import AbstractWorkerHolder
from mapadroid.db.model import TrsStatsDetectWildMonRaw


class MonEntry(TrsStatsDetectWildMonRaw):
    def __init__(self, worker: str, encounter_id: int, first_scanned: datetime):
        super().__init__()
        self.worker = worker
        self.encounter_id = encounter_id
        self.count = 0
        self.is_shiny = False
        self.first_seen = first_scanned
        self.last_scanned = first_scanned

    def update(self, last_scanned: datetime, is_shiny: bool = False) -> None:
        if is_shiny:
            self.is_shiny = True
        self.count += 1
        self.last_scanned = last_scanned


class WildMonStatsHolder(AbstractStatsHolder, AbstractWorkerHolder):
    def __init__(self, worker: str):
        # Wild mon encounterID to counts seen mapping
        AbstractWorkerHolder.__init__(self, worker)
        self._wild_mons_seen: Dict[int, MonEntry] = {}

    async def submit(self, session: AsyncSession) -> None:
        for encounter_id, mon_entry in self._wild_mons_seen.items():
            async with session.begin_nested() as nested:
                session.add(mon_entry)
                await nested.commit()
                # TODO: Catch IntegrityError/handle update

    def add(self, encounter_id: int, scanned: datetime, is_shiny: bool = False) -> None:
        if encounter_id not in self._wild_mons_seen:
            self._wild_mons_seen[encounter_id] = MonEntry(self._worker, encounter_id, scanned)
        else:
            self._wild_mons_seen[encounter_id].update(scanned, is_shiny)
