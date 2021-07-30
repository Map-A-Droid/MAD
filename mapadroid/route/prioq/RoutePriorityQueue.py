import asyncio
import copy
import heapq
import time
from asyncio import Task
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

from loguru import logger

from mapadroid.route.prioq.AbstractRoutePriorityQueueStrategy import AbstractRoutePriorityQueueStrategy, \
    RoutePriorityQueueEntry


class RoutePriorityQueue:
    def __init__(self, strategy: AbstractRoutePriorityQueueStrategy):
        self._strategy: AbstractRoutePriorityQueueStrategy = strategy
        self._update_lock: asyncio.Lock = asyncio.Lock()
        self.__queue: List[RoutePriorityQueueEntry] = []
        self._stop_updates: asyncio.Event = asyncio.Event()
        self._update_prio_queue_task: Optional[Task] = None

    async def start(self):
        await self._start_priority_queue()

    async def stop(self):
        self._stop_updates.set()
        if self._update_prio_queue_task:
            self._update_prio_queue_task.cancel()

    async def _start_priority_queue(self):
        loop = asyncio.get_running_loop()
        if not self._update_prio_queue_task:
            self._update_prio_queue_task = loop.create_task(self._update_priority_queue_loop())
            logger.info("Started PrioQ")

    async def _update_priority_queue_loop(self):
        if self.strategy.get_update_interval() is None or self.strategy.get_update_interval() == 0:
            return
        while not self._stop_updates.is_set():
            # retrieve the latest hatches from DB
            logger.success("Trying to update prioQ")
            await self.__update_queue()
            await asyncio.sleep(self.strategy.get_update_interval())

    @property
    def strategy(self) -> AbstractRoutePriorityQueueStrategy:
        return self._strategy

    @strategy.setter
    def strategy(self, strategy: AbstractRoutePriorityQueueStrategy) -> None:
        self._strategy = strategy

    async def pop_event(self) -> RoutePriorityQueueEntry:
        """
        Pops a coord off the queue if applicable, else None
        Returns: RoutePriorityQueueEntry if one is available
        Raises: IndexError if no coord is available
        Raises asyncio.TimeoutError if an update if blocking the prioQ event retrieval

        """
        # At most wait 500ms to retrieve a prioQ event location
        coord = await asyncio.wait_for(self.__pop_event_internal(), 1)
        return coord

    async def __pop_event_internal(self) -> RoutePriorityQueueEntry:
        async with self._update_lock:
            if not self.__queue:
                raise IndexError("No items in queue")
            elif self.__queue[0].timestamp_due > int(time.time()):
                raise IndexError("No item available that is due at this time")
            else:
                coord = heapq.heappop(self.__queue)
                logger.info("Got event: {}", coord)
                return coord

    def __merge_queues(self, old_coords: List[RoutePriorityQueueEntry],
                       new_coords: List[RoutePriorityQueueEntry]) -> List[RoutePriorityQueueEntry]:
        # TODO: For each new coord search for old coord given timedelta and distance whether it can be
        #  considered to cluster
        # just remove all coords < max backlog time and all > NOW. Append all new coords...
        now = int(time.time())
        merged_coords = [coord for coord in old_coords if
                         now >= coord.timestamp_due
                         and (self._strategy.get_max_backlog_duration() == 0
                              or coord.timestamp_due > now - self._strategy.get_max_backlog_duration())]
        merged_coords.extend(new_coords)
        return merged_coords

    async def __update_queue(self) -> None:
        new_coords: List[RoutePriorityQueueEntry] = await self._strategy.retrieve_new_coords()
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor() as pool:
            post_processed_coords: List[RoutePriorityQueueEntry] = await loop.run_in_executor(
                pool, self.strategy.postprocess_coords, new_coords)
        logger.success("Got {} new events", len(post_processed_coords))
        async with self._update_lock:
            with ThreadPoolExecutor() as pool:
                merged = await loop.run_in_executor(
                    pool, self.__merge_filter_queue, post_processed_coords)
            self.__queue = merged

    def __merge_filter_queue(self, post_processed_coords: List[RoutePriorityQueueEntry]):
        if self.strategy.is_full_replace_queue():
            merged = post_processed_coords
        else:
            merged = self.__merge_queues(self.__queue, post_processed_coords)
        merged = self._strategy.filter_queue(merged)
        heapq.heapify(merged)
        return merged

    def get_copy_of_prioq(self) -> List[RoutePriorityQueueEntry]:
        copied_queue = copy.deepcopy(self.__queue)
        ordinary_list: List[RoutePriorityQueueEntry] = []
        while copied_queue:
            ordinary_list.append(heapq.heappop(copied_queue))
        return ordinary_list
