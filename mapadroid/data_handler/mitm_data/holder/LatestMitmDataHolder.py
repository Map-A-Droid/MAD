from typing import Dict, Any, Optional

from mapadroid.data_handler.AbstractWorkerHolder import AbstractWorkerHolder
from mapadroid.utils.collections import Location


class LatestMitmDataHolderEntry:
    def __init__(self, location: Optional[Location], timestamp_received: Optional[int],
                 timestamp_of_data_retrieval: Optional[int], data: Any):
        self.location: Optional[Location] = location
        # The time MAD received the data from a device/worker
        self.timestamp_received: Optional[int] = timestamp_received
        # The time that the device/worker received the data
        self.timestamp_of_data_retrieval: Optional[int] = timestamp_of_data_retrieval
        # TODO: Eventually move down using a hierarchy...
        #  And split protos vs latestmitm settings...
        self.data: Any = data


class LatestMitmDataHolder(AbstractWorkerHolder):
    def __init__(self, worker: str):
        # Wild mon encounterID to counts seen mapping
        AbstractWorkerHolder.__init__(self, worker)
        self.__entries: Dict[str, LatestMitmDataHolderEntry] = {}

    def update(self, key: str, value: Any, timestamp_received: Optional[int] = None,
               timestamp_of_data_retrieval: Optional[int] = None,
               location: Optional[Location] = None) -> None:
        self.__entries[key] = LatestMitmDataHolderEntry(location, timestamp_received,
                                                        timestamp_of_data_retrieval, value)

    def get_latest(self, key: str) -> Optional[LatestMitmDataHolderEntry]:
        return self.__entries.get(key)

    def get_all(self) -> Dict[str, LatestMitmDataHolderEntry]:
        return self.__entries
