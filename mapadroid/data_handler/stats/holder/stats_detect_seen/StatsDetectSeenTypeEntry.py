from datetime import datetime

from mapadroid.db.model import TrsStatsDetectSeenType


class StatsDetectSeenTypeEntry(TrsStatsDetectSeenType):
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
