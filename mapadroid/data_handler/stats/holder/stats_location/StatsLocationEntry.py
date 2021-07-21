import time

from mapadroid.db.model import TrsStatsLocation


class StatsLocationEntry(TrsStatsLocation):
    def __init__(self, worker: str):
        super().__init__()
        self.worker = worker
        self.timestamp_scan = int(time.time())
        self.location_ok = 0
        self.location_nok = 0

    def update(self, time_of_scan: int, location_ok: bool):
        self.timestamp_scan = time_of_scan
        if location_ok:
            self.location_ok += 1
        else:
            self.location_nok += 1

