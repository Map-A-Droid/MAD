from datetime import datetime
from typing import Dict

import sqlalchemy
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.data_handler.stats.holder.AbstractStatsHolder import AbstractStatsHolder
from mapadroid.data_handler.stats.holder.stats_detect_seen.StatsDetectSeenTypeEntry import StatsDetectSeenTypeEntry
from mapadroid.db.helper.TrsStatsDetectSeenTypeHelper import TrsStatsDetectSeenTypeHelper
from mapadroid.utils.madGlobals import MonSeenTypes


class StatsDetectSeenTypeHolder(AbstractStatsHolder):
    def __init__(self):
        self._entries: Dict[int, StatsDetectSeenTypeEntry] = {}

    async def submit(self, session: AsyncSession) -> None:
        for encounter_id, stat_entry in self._entries.items():
            async with session.begin_nested() as nested:
                try:
                    await TrsStatsDetectSeenTypeHelper.create_or_update(session, stat_entry)
                    await nested.commit()
                except sqlalchemy.exc.IntegrityError as e:
                    logger.warning("Failed submitting seen type stats. {}", e)
                    await nested.rollback()
        del self._entries

    def __ensure_entry_available(self, encounter_id: int) -> StatsDetectSeenTypeEntry:
        if encounter_id not in self._entries:
            self._entries[encounter_id] = StatsDetectSeenTypeEntry(encounter_id)
        return self._entries[encounter_id]

    def add(self, encounter_id: int, type_of_detection: MonSeenTypes, time_of_scan: datetime) -> None:
        entry: StatsDetectSeenTypeEntry = self.__ensure_entry_available(encounter_id)
        if type_of_detection == MonSeenTypes.encounter:
            entry.update(encounter=time_of_scan)
        elif type_of_detection == MonSeenTypes.wild:
            entry.update(wild=time_of_scan)
        elif type_of_detection == MonSeenTypes.nearby_stop:
            entry.update(nearby_stop=time_of_scan)
        elif type_of_detection == MonSeenTypes.nearby_cell:
            entry.update(nearby_cell=time_of_scan)
        elif type_of_detection == MonSeenTypes.lure_encounter:
            entry.update(lure_encounter=time_of_scan)
        elif type_of_detection == MonSeenTypes.lure_wild:
            entry.update(lure_wild=time_of_scan)
