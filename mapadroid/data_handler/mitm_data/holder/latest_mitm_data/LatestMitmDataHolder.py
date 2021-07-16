from typing import Dict, Any, Optional

from mapadroid.data_handler.AbstractWorkerHolder import AbstractWorkerHolder
from mapadroid.data_handler.mitm_data.holder.latest_mitm_data.LatestMitmDataEntry import LatestMitmDataEntry
from mapadroid.utils.collections import Location


class LatestMitmDataHolder(AbstractWorkerHolder):
    def __init__(self, worker: str):
        # Wild mon encounterID to counts seen mapping
        AbstractWorkerHolder.__init__(self, worker)
        self.__entries: Dict[str, LatestMitmDataEntry] = {}

    def update(self, key: str, value: Any, timestamp_received: Optional[int] = None,
               timestamp_of_data_retrieval: Optional[int] = None,
               location: Optional[Location] = None) -> None:
        self.__entries[key] = LatestMitmDataEntry(location, timestamp_received,
                                                  timestamp_of_data_retrieval, value)

    def get_latest(self, key: str) -> Optional[LatestMitmDataEntry]:
        return self.__entries.get(key)

    def get_all(self) -> Dict[str, LatestMitmDataEntry]:
        return self.__entries
