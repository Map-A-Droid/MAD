from abc import ABC, abstractmethod
from typing import List, Optional

from dataclasses import dataclass, field

from mapadroid.utils.collections import Location


@dataclass(order=True)
class RoutePriorityQueueEntry:
    # Timestamp due basically is the timestamp of the last event clustered in
    timestamp_due: int
    location: Location = field(compare=False)


class AbstractRoutePriorityQueueStrategy(ABC):
    def __init__(self, update_interval: int,
                 full_replace_queue: bool, max_backlog_duration: int,
                 delay_after_event: int):
        self._update_interval: int = update_interval
        self._full_replace_queue: bool = full_replace_queue
        self._max_backlog_duration: Optional[int] = max_backlog_duration
        self._delay_after_event: int = delay_after_event

    def get_delay_after_event(self) -> int:
        return self._delay_after_event

    def get_update_interval(self) -> int:
        """

        Returns: The seconds to sleep inbetween updates

        """
        return self._update_interval

    def is_full_replace_queue(self) -> bool:
        """

        Returns: boolean indicating whether the queue is supposed to be replaced with every update (i.e. old entries are
        to be deleted) or merged.

        """
        return self._full_replace_queue

    def get_max_backlog_duration(self) -> int:
        return self._max_backlog_duration if self._max_backlog_duration else 300

    @abstractmethod
    async def retrieve_new_coords(self) -> List[RoutePriorityQueueEntry]:
        """

        Returns: List of RoutePriorityQueueEntry representing the next events to schedule

        """
        pass

    @abstractmethod
    def filter_queue(self, queue: List[RoutePriorityQueueEntry]) -> List[RoutePriorityQueueEntry]:
        """

        Args:
            queue:

        Returns:

        """
        pass

    @abstractmethod
    def postprocess_coords(self, coords: List[RoutePriorityQueueEntry]) -> List[RoutePriorityQueueEntry]:
        """
        E.g. clustering to pe applied to coords after retrieval
        Args:
            coords:

        Returns:

        """
        pass
