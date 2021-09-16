from typing import Optional, Any, Union

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
