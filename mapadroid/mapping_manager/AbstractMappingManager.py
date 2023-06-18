from abc import ABC, abstractmethod
from typing import List, Set, Optional, Dict


class AbstractMappingManager(ABC):
    @abstractmethod
    async def get_all_loaded_origins(self) -> Set[str]:
        pass

    @abstractmethod
    async def get_safe_items(self, origin: str) -> List[int]:
        pass

    @abstractmethod
    async def get_auths(self) -> Optional[Dict[str, str]]:
        pass

    @abstractmethod
    async def routemanager_of_origin_is_levelmode(self, origin: str) -> bool:
        pass

    @abstractmethod
    async def routemanager_get_quest_layer_to_scan_of_origin(self, origin: str) -> Optional[int]:
        pass

    @abstractmethod
    async def increment_login_tracking_by_origin(self, origin: str) -> bool:
        pass
