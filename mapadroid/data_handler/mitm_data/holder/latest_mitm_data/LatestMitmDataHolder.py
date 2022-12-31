from typing import Dict, List, Optional, Union

from mapadroid.data_handler.AbstractWorkerHolder import AbstractWorkerHolder
from mapadroid.data_handler.mitm_data.holder.latest_mitm_data.LatestMitmDataEntry import \
    LatestMitmDataEntry
from mapadroid.utils.collections import Location


class LatestMitmDataHolder(AbstractWorkerHolder):
    def __init__(self, worker: str):
        # Wild mon encounterID to counts seen mapping
        AbstractWorkerHolder.__init__(self, worker)
        self.__entries: Dict[Union[int, str], LatestMitmDataEntry] = {}

    def update(self, key: Union[int, str], value: Union[List, Dict], timestamp_received: Optional[int] = None,
               timestamp_of_data_retrieval: Optional[int] = None,
               location: Optional[Location] = None) -> None:
        latest_entry: Optional[LatestMitmDataEntry] = self.__entries.get(key)
        if (latest_entry and latest_entry.timestamp_received
                and (not timestamp_of_data_retrieval
                     or latest_entry.timestamp_of_data_retrieval > timestamp_of_data_retrieval)):
            # Ignore update as it yields an older timestamp than the one known to us
            return
        if key in self.__entries:
            del self.__entries[key]
        self.__entries[key] = LatestMitmDataEntry(location, timestamp_received,
                                                  timestamp_of_data_retrieval, value)

    def get_latest(self, key: Union[int, str]) -> Optional[LatestMitmDataEntry]:
        return self.__entries.get(key)

    def get_all(self) -> Dict[Union[int, str], LatestMitmDataEntry]:
        return self.__entries
