import asyncio
from asyncio import Task
from typing import List

from loguru import logger

from mapadroid.data_handler.mitm_data.AbstractMitmMapper import AbstractMitmMapper
from mapadroid.data_handler.stats.AbstractStatsHandler import AbstractStatsHandler
from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.mitm_receiver.SerializedMitmDataProcessor import \
    SerializedMitmDataProcessor
from mapadroid.utils.madGlobals import application_args
from mapadroid.utils.questGen import QuestGen


class MitmDataProcessorManager:
    def __init__(self, mitm_mapper: AbstractMitmMapper, stats_handler: AbstractStatsHandler,
                 db_wrapper: DbWrapper, quest_gen: QuestGen):
        self._worker_threads: List[Task] = []
        self._mitm_data_queue: asyncio.Queue = asyncio.Queue()
        self._mitm_mapper: AbstractMitmMapper = mitm_mapper
        self._stats_handler: AbstractStatsHandler = stats_handler
        self._db_wrapper: DbWrapper = db_wrapper
        self._quest_gen: QuestGen = quest_gen

    def get_queue(self) -> asyncio.Queue:
        return self._mitm_data_queue

    async def launch_processors(self):
        loop = asyncio.get_running_loop()
        for i in range(application_args.mitmreceiver_data_workers):
            data_processor: SerializedMitmDataProcessor = SerializedMitmDataProcessor(
                self._mitm_data_queue,
                self._stats_handler,
                self._mitm_mapper,
                self._db_wrapper,
                self._quest_gen,
                name="DataProc-%s" % str(i))
            # TODO: Own thread/loop?
            self._worker_threads.append(loop.create_task(data_processor.run()))

    async def shutdown(self):
        # TODO: Stop accepting data in the queue...
        if self._mitm_data_queue is not None:
            await self._mitm_data_queue.join()

        logger.info("Stopping {} MITM data processors", len(self._worker_threads))
        for worker_thread in self._worker_threads:
            worker_thread.cancel()
        logger.info("Stopped MITM data processors")
