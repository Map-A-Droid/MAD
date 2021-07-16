from datetime import datetime
from typing import Dict

from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.data_handler.stats.holder.AbstractStatsHolder import AbstractStatsHolder
from mapadroid.data_handler.AbstractWorkerHolder import AbstractWorkerHolder
from mapadroid.data_handler.stats.holder.wild_mon_stats.WildMonStatsEntry import WildMonStatsEntry


class WildMonStatsHolder(AbstractStatsHolder, AbstractWorkerHolder):
    def __init__(self, worker: str):
        # Wild mon encounterID to counts seen mapping
        AbstractWorkerHolder.__init__(self, worker)
        self._wild_mons_seen: Dict[int, WildMonStatsEntry] = {}

    async def submit(self, session: AsyncSession) -> None:
        for encounter_id, mon_entry in self._wild_mons_seen.items():
            async with session.begin_nested() as nested:
                session.add(mon_entry)
                await nested.commit()
                # TODO: Catch IntegrityError/handle update

    def add(self, encounter_id: int, scanned: datetime, is_shiny: bool = False) -> None:
        if encounter_id not in self._wild_mons_seen:
            self._wild_mons_seen[encounter_id] = WildMonStatsEntry(self._worker, encounter_id, scanned)
        else:
            self._wild_mons_seen[encounter_id].update(scanned, is_shiny)
