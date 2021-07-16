import time
from datetime import datetime

from mapadroid.db.model import TrsStatsDetect


class StatsDetectEntry(TrsStatsDetect):
    def __init__(self, worker: str):
        super().__init__()
        self.worker = worker
        self.timestamp_scan = time.time()
        self.mon = 0
        self.raid = 0
        self.mon_iv = 0
        self.quest = 0

    def update(self, time_scanned: datetime, new_mons: int = 0, new_raids: int = 0, new_mon_ivs: int = 0,
               new_quests: int = 0):
        self.mon += new_mons
        self.raid += new_raids
        self.mon_iv += new_mon_ivs
        self.quest += new_quests
        if time_scanned.timestamp() > self.timestamp_scan:
            self.timestamp_scan = time_scanned.timestamp()
