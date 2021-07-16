from datetime import datetime
from typing import Dict

from mapadroid.data_handler.stats.holder.AbstractStatsHolder import AbstractStatsHolder
from mapadroid.data_handler.stats.holder.stats_detect_seen.StatsDetectSeenTypeEntry import StatsDetectSeenTypeEntry
from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.utils.madGlobals import MonSeenTypes


class StatsDetectSeenTypeHolder(AbstractStatsHolder):
    def __init__(self):
        self._entries: Dict[int, StatsDetectSeenTypeEntry] = {}

    async def submit(self, session: AsyncSession) -> None:
        for encounter_id, stat_entry in self._entries.items():
            async with session.begin_nested() as nested:
                session.add(stat_entry)
                await nested.commit()
                # TODO: Catch IntegrityError/handle update

    def __ensure_entry_available(self, encounter_id: int) -> StatsDetectSeenTypeEntry:
        if encounter_id not in self._entries:
            self._entries[encounter_id] = StatsDetectSeenTypeEntry(encounter_id)
        return self._entries[encounter_id]

    def add(self, encounter_id: int, type_of_detection: MonSeenTypes, time_of_scan: datetime) -> None:
        entry: StatsDetectSeenTypeEntry = self.__ensure_entry_available(encounter_id)
        if type_of_detection == MonSeenTypes.ENCOUNTER:
            entry.update(encounter=time_of_scan)
        elif type_of_detection == MonSeenTypes.WILD:
            entry.update(wild=time_of_scan)
        elif type_of_detection == MonSeenTypes.NEARBY_STOP:
            entry.update(nearby_stop=time_of_scan)
        elif type_of_detection == MonSeenTypes.NEARBY_CELL:
            entry.update(nearby_cell=time_of_scan)
        elif type_of_detection == MonSeenTypes.LURE_ENCOUNTER:
            entry.update(lure_encounter=time_of_scan)
        elif type_of_detection == MonSeenTypes.LURE_WILD:
            entry.update(lure_wild=time_of_scan)
