from __future__ import annotations

from typing import Optional, Any, Union, Dict

import ujson

from mapadroid.utils.collections import Location


class LatestMitmDataEntry:
    def __init__(self, location: Optional[Location], timestamp_received: Optional[int],
                 timestamp_of_data_retrieval: Optional[int], data: Optional[Any]):
        self.location: Optional[Location] = location
        # The time MAD received the data from a device/worker
        self.timestamp_received: Optional[int] = timestamp_received
        # The time that the device/worker received the data
        self.timestamp_of_data_retrieval: Optional[int] = timestamp_of_data_retrieval
        # TODO: Eventually move down using a hierarchy...
        #  And split protos vs latestmitm settings...
        self.data: Optional[Union[list, dict]] = data

    @staticmethod
    async def from_json(json_data: str) -> Optional[LatestMitmDataEntry]:
        # TODO: asyncexec
        loaded: Dict = ujson.loads(json_data)
        if not loaded:
            return None
        location_raw = loaded.get("location", None)
        location: Optional[Location] = None
        if location_raw:
            location = Location(location_raw[0], location_raw[1])
        timestamp_received: Optional[int] = loaded.get("timestamp_received")
        timestamp_of_data_retrieval: Optional[int] = loaded.get("timestamp_of_data_retrieval")
        data: Optional[Union[list, dict]] = loaded.get("data")
        obj: LatestMitmDataEntry = LatestMitmDataEntry(location,
                                                       timestamp_received,
                                                       timestamp_of_data_retrieval,
                                                       data)
        return obj

    async def to_json(self) -> str:
        return ujson.dumps(self, default=lambda o: o.__dict__)
