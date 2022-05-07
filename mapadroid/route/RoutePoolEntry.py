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
    rounds: int = 0
    current_pos: Location = Location(0.0, 0.0)
    prio_coord: Optional[Location] = None
    worker_sleeping: float = 0
    last_position_type: PositionType = PositionType.NORMAL
    queue: collections.deque = collections.deque()
