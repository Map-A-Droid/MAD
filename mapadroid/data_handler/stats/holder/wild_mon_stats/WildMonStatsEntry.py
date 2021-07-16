from datetime import datetime

from mapadroid.db.model import TrsStatsDetectWildMonRaw


class WildMonStatsEntry(TrsStatsDetectWildMonRaw):
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

