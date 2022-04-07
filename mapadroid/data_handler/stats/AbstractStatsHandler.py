from abc import abstractmethod, ABC
from datetime import datetime
from typing import List, Optional

from mapadroid.utils.collections import Location
from mapadroid.utils.madGlobals import PositionType, TransportType, MonSeenTypes
from mapadroid.worker.WorkerType import WorkerType


class AbstractStatsHandler(ABC):
    # ##
    # Stats related methods
    # ##
    async def start(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    @abstractmethod
    async def stats_collect_wild_mon(self, worker: str, encounter_ids: List[int], time_scanned: datetime) -> None:
        pass

    @abstractmethod
    async def stats_collect_mon_iv(self, worker: str, encounter_id: int, time_scanned: datetime,
                                   is_shiny: bool) -> None:
        pass

    @abstractmethod
    async def stats_collect_quest(self, worker: str, time_scanned: datetime) -> None:
        pass

    @abstractmethod
    async def stats_collect_raid(self, worker: str, time_scanned: datetime, amount_raids: int = 1) -> None:
        pass

    @abstractmethod
    async def stats_collect_location_data(self, worker: str, location: Optional[Location], success: bool,
                                          fix_timestamp: int,
                                          position_type: PositionType, data_timestamp: int, worker_type: WorkerType,
                                          transport_type: TransportType, timestamp_of_record: int) -> None:
        pass

    @abstractmethod
    async def stats_collect_seen_type(self, encounter_ids: List[int], type_of_detection: MonSeenTypes,
                                      time_of_scan: datetime) -> None:
        pass
