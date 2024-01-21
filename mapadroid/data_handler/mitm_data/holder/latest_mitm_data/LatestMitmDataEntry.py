from __future__ import annotations

import base64
from typing import Dict, List, Optional, Union

from orjson import orjson

from mapadroid.utils.collections import Location


class LatestMitmDataEntry:
    def __init__(self, location: Optional[Location], timestamp_received: Optional[int],
                 timestamp_of_data_retrieval: Optional[int], data: Union[List, Dict, bytes]):
        self.location: Optional[Location] = location
        # The time MAD received the data from a device/worker
        self.timestamp_received: Optional[int] = timestamp_received
        # The time that the device/worker received the data
        self.timestamp_of_data_retrieval: Optional[int] = timestamp_of_data_retrieval
        self.data: Union[List, Dict, bytes] = data

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
        # TODO: Likely data is a str which needs to be translated to bytes?
        raw_data: Optional[Union[List, Dict, bytes, str]] = loaded.get("data")
        if not raw_data:
            return None
        elif isinstance(raw_data, str):
            data: Union[List, Dict, bytes] = base64.b64decode(raw_data)
        else:
            data: Union[List, Dict, bytes] = raw_data
        obj: LatestMitmDataEntry = LatestMitmDataEntry(location,
                                                       timestamp_received,
                                                       timestamp_of_data_retrieval,
                                                       data)
        return obj

    async def to_json(self) -> bytes:
        if isinstance(self.data, bytes):
            self.data = str(base64.b64encode(self.data))
        return orjson.dumps(self.__dict__)
