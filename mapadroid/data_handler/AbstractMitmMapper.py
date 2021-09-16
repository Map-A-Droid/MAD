from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional, Dict, Union, Any

from mapadroid.data_handler.mitm_data.holder.latest_mitm_data.LatestMitmDataEntry import LatestMitmDataEntry
from mapadroid.utils.collections import Location
from mapadroid.utils.madGlobals import PositionType, TransportType, MonSeenTypes
from mapadroid.worker.WorkerType import WorkerType


class AbstractMitmMapper(ABC):
    # ##
    # Stats related methods
    # ##
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
    async def stats_collect_raid(self, worker: str, time_scanned: datetime) -> None:
        pass

    @abstractmethod
    async def stats_collect_location_data(self, worker: str, location: Location, success: bool, fix_timestamp: int,
                                          position_type: PositionType, data_timestamp: int, worker_type: WorkerType,
                                          transport_type: TransportType, timestamp_of_record: int) -> None:
        pass

    @abstractmethod
    async def stats_collect_seen_type(self, encounter_ids: List[int], type_of_detection: MonSeenTypes,
                                      time_of_scan: datetime) -> None:
        pass

    # ##
    # Data related methods
    # ##
    @abstractmethod
    async def get_last_possibly_moved(self, worker: str) -> int:
        pass

    @abstractmethod
    async def update_latest(self, worker: str, key: str, value: Any, timestamp_received_raw: float = None,
                            timestamp_received_receiver: float = None, location: Location = None) -> None:
        pass

    @abstractmethod
    async def request_latest(self, worker: str, key: str) -> Optional[LatestMitmDataEntry]:
        pass

    @abstractmethod
    async def get_full_latest_data(self, worker: str) -> Dict[Union[int, str], LatestMitmDataEntry]:
        pass

    @abstractmethod
    async def get_poke_stop_visits(self, worker: str) -> int:
        pass

    @abstractmethod
    async def get_level(self, worker: str) -> int:
        pass

    @abstractmethod
    async def get_injection_status(self, worker: str) -> bool:
        pass

    @abstractmethod
    async def set_injection_status(self, worker: str, status: bool) -> None:
        pass

    @abstractmethod
    async def get_last_known_location(self, worker: str) -> Optional[Location]:
        pass

    @abstractmethod
    async def set_level(self, worker: str, level: int) -> None:
        pass

    @abstractmethod
    async def set_pokestop_visits(self, worker: str, pokestop_visits: int) -> None:
        pass
