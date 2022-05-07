import collections
from dataclasses import dataclass
from typing import List, Optional

from mapadroid.utils.collections import Location
from mapadroid.utils.madGlobals import PositionType


@dataclass
class RoutePoolEntry:
    last_access: float
    subroute: List[Location]
    time_added: float
    # The queue needs to be created in the calling code as a global queue would be used otherwise...
    queue: collections.deque
    rounds: int
    current_pos: Location
    prio_coord: Optional[Location]
    worker_sleeping: float
    last_position_type: PositionType
