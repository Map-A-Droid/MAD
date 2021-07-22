import asyncio
import threading
import time
from asyncio import Task
from typing import List

from mapadroid.data_handler.MitmMapper import MitmMapper
from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.mitm_receiver.SerializedMitmDataProcessor import \
    SerializedMitmDataProcessor
from mapadroid.utils.logging import LoggerEnums, get_logger

logger = get_logger(LoggerEnums.mitm)


class MitmDataProcessorManager():
    def __init__(self, args, mitm_mapper: MitmMapper, db_wrapper: DbWrapper):
        self._worker_threads: List[Task] = []
        self._args = args
        self._mitm_data_queue: asyncio.Queue = asyncio.Queue()
        self._mitm_mapper: MitmMapper = mitm_mapper
        self._db_wrapper: DbWrapper = db_wrapper
        self._queue_check_thread = None
        self._stop_queue_check_thread = False

        self._queue_check_thread = threading.Thread(target=self._queue_size_check, args=())
        self._queue_check_thread.daemon = True
        self._queue_check_thread.start()

    def get_queue(self) -> asyncio.Queue:
        return self._mitm_data_queue

    def get_queue_size(self):
        # for whatever reason, there's no actual implementation of qsize()
        # on MacOS. There are better solutions for this but c'mon, who is
        # running MAD on MacOS anyway?
        try:
            item_count = self._mitm_data_queue.qsize()
        except NotImplementedError:
            item_count = 0

        return item_count

    def _queue_size_check(self):
        while not self._stop_queue_check_thread:
            item_count = self.get_queue_size()
            if item_count > 50:
                logger.warning("MITM data processing workers are falling behind! Queue length: {}", item_count)

            time.sleep(3)

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
        self._stop_queue_check_thread = True
        if self._mitm_data_queue is not None:
            await self._mitm_data_queue.join()

        logger.info("Stopping {} MITM data processors", len(self._worker_threads))
        for worker_thread in self._worker_threads:
            worker_thread.cancel()
        logger.info("Stopped MITM data processors")
