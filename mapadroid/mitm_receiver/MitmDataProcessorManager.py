import asyncio
from asyncio import Task
from typing import List

from mapadroid.data_handler.MitmMapper import MitmMapper
from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.mitm_receiver.SerializedMitmDataProcessor import \
    SerializedMitmDataProcessor
from loguru import logger


class MitmDataProcessorManager():
    def __init__(self, args, mitm_mapper: MitmMapper, db_wrapper: DbWrapper):
        self._worker_threads: List[Task] = []
        self._args = args
        self._mitm_data_queue: asyncio.Queue = asyncio.Queue()
        self._mitm_mapper: MitmMapper = mitm_mapper
        self._db_wrapper: DbWrapper = db_wrapper

    def get_queue(self) -> asyncio.Queue:
        return self._mitm_data_queue

    async def launch_processors(self):
        loop = asyncio.get_running_loop()
        for i in range(self._args.mitmreceiver_data_workers):
            data_processor: SerializedMitmDataProcessor = SerializedMitmDataProcessor(
                self._mitm_data_queue,
                self._args,
                self._mitm_mapper,
                self._db_wrapper,
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
