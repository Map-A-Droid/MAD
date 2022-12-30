from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union

from mapadroid.data_handler.mitm_data.holder.latest_mitm_data.LatestMitmDataEntry import \
    LatestMitmDataEntry
from mapadroid.utils.collections import Location


class AbstractMitmMapper(ABC):
    # ##
    # Data related methods
    # ##
    @abstractmethod
    async def get_last_possibly_moved(self, worker: str) -> int:
        pass

    @abstractmethod
    async def update_latest(self, worker: str, key: str, value: Union[List, Dict],
                            timestamp_received_raw: float = None,
                            timestamp_received_receiver: float = None, location: Location = None) -> None:
        pass

    @abstractmethod
    async def request_latest(self, worker: str, key: str,
                             timestamp_earliest: Optional[int] = None) -> Optional[LatestMitmDataEntry]:
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

    @abstractmethod
    async def set_quests_held(self, worker: str, quests_held: Optional[List[int]]) -> None:
        pass

    @abstractmethod
    async def get_quests_held(self, worker: str) -> Optional[List[int]]:
        pass
