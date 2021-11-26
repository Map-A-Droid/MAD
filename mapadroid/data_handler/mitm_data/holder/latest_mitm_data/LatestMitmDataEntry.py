from __future__ import annotations

from typing import Optional, Any, Union, Dict

from orjson import orjson

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
    async def from_json(json_data: Union[bytes, str]) -> Optional[LatestMitmDataEntry]:
        # TODO: asyncexec
        loaded: Dict = orjson.loads(json_data)
        if not loaded:
            return None
        location_raw = loaded.get("location", None)
        location: Optional[Location] = None
        if location_raw:
            if isinstance(location_raw, list):
                location = Location(location_raw[0], location_raw[1])
            elif isinstance(location_raw, dict):
                lat = location_raw.get("lat", 0.0)
                lng = location_raw.get("lng", 0.0)
                location = Location(lat, lng)

        timestamp_received: Optional[int] = loaded.get("timestamp_received")
        timestamp_of_data_retrieval: Optional[int] = loaded.get("timestamp_of_data_retrieval")
        data: Optional[Union[list, dict]] = loaded.get("data")
        obj: LatestMitmDataEntry = LatestMitmDataEntry(location,
                                                       timestamp_received,
                                                       timestamp_of_data_retrieval,
                                                       data)
        return obj

    async def to_json(self) -> bytes:
        return orjson.dumps(self.__dict__)
