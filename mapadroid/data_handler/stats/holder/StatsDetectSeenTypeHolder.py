from datetime import datetime
from typing import Dict

from mapadroid.data_handler.stats.holder.AbstractStatsHolder import AbstractStatsHolder
from mapadroid.db.model import TrsStatsDetectSeenType
from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.utils.madGlobals import MonSeenTypes


class StatsDetectEntry(TrsStatsDetectSeenType):
    def __init__(self, encounter_id: int):
        super().__init__()
        self.encounter_id = encounter_id
        self.encounter = None
        self.wild = None
        self.nearby_stop = None
        self.nearby_cell = None
        self.lure_encounter = None
        self.lure_wild = None

    def update(self, encounter: datetime = None,
               wild: datetime = None, nearby_stop: datetime = None,
               nearby_cell: datetime = None, lure_encounter: datetime = None,
               lure_wild: datetime = None):
        if encounter:
            self.encounter = encounter
        if wild:
            self.wild = wild
        if nearby_stop:
            self.nearby_stop = nearby_stop
        if nearby_cell:
            self.nearby_cell = nearby_cell
        if lure_encounter:
            self.lure_encounter = lure_encounter
        if lure_wild:
            self.lure_wild = lure_wild


class StatsDetectSeenTypeHolder(AbstractStatsHolder):
    def __init__(self):
        self._entries: Dict[int, StatsDetectEntry] = {}

    async def submit(self, session: AsyncSession) -> None:
        for encounter_id, stat_entry in self._entries.items():
            async with session.begin_nested() as nested:
                session.add(stat_entry)
                await nested.commit()
                # TODO: Catch IntegrityError/handle update

    def __ensure_entry_available(self, encounter_id: int) -> StatsDetectEntry:
        if encounter_id not in self._entries:
            self._entries[encounter_id] = StatsDetectEntry(encounter_id)
        return self._entries[encounter_id]

    def add(self, encounter_id: int, type_of_detection: MonSeenTypes, time_of_scan: datetime) -> None:
        entry: StatsDetectEntry = self.__ensure_entry_available(encounter_id)
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
