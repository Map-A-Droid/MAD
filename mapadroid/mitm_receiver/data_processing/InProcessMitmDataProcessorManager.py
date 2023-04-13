import asyncio
from asyncio import Task
from multiprocessing import Process
from typing import List, Optional

from loguru import logger

from mapadroid.account_handler.AbstractAccountHandler import \
    AbstractAccountHandler
from mapadroid.data_handler.mitm_data.AbstractMitmMapper import \
    AbstractMitmMapper
from mapadroid.data_handler.stats.AbstractStatsHandler import \
    AbstractStatsHandler
from mapadroid.db.DbFactory import DbFactory
from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.mitm_receiver.data_processing.AbstractMitmDataProcessingManager import \
    AbstractMitmDataProcessingManager
from mapadroid.mitm_receiver.data_processing.SerializedMitmDataProcessor import \
    SerializedMitmDataProcessor
from mapadroid.utils.madGlobals import application_args
from mapadroid.utils.questGen import QuestGen


class InProcessMitmDataProcessorManager(AbstractMitmDataProcessingManager, Process):
    _db_wrapper: Optional[DbWrapper]
    _worker_threads: List[Task]
    _mitm_mapper: AbstractMitmMapper
    _stats_handler: AbstractStatsHandler
    _quest_gen: QuestGen
    """
    Within a process, an asyncio loop is run which processes data right away.
    This class handles the creation of the data processors themselves to handle the data processing in order to have
     a shared queue.
    """
    def __init__(self, mitm_mapper: AbstractMitmMapper, stats_handler: AbstractStatsHandler, db_wrapper: DbWrapper,
                 quest_gen: QuestGen, account_handler: AbstractAccountHandler):
        super(InProcessMitmDataProcessorManager, self).__init__()
        super(Process, self).__init__()
        self._worker_threads: List[Task] = []
        self._mitm_mapper: AbstractMitmMapper = mitm_mapper
        self._stats_handler: AbstractStatsHandler = stats_handler
        self._db_wrapper = db_wrapper
        self._quest_gen: QuestGen = quest_gen
        self._account_handler: AbstractAccountHandler = account_handler

    def run(self):
        try:
            to_exec = self.launch_processors()
            asyncio.run(to_exec, debug=True)
        except (KeyboardInterrupt, Exception) as e:
            # shutdown(loop_being_run)
            logger.info(f"Shutting down. {e}")
            logger.exception(e)

    async def launch_processors(self):
        db_exec = None
        if not self._db_wrapper:
            db_wrapper, db_exec = await DbFactory.get_wrapper(application_args,
                                                              application_args.mitmreceiver_data_workers * 2)
            self._db_wrapper = db_wrapper
        loop = asyncio.get_running_loop()
        for i in range(application_args.mitmreceiver_data_workers):
            data_processor: SerializedMitmDataProcessor = SerializedMitmDataProcessor(
                self._mitm_data_queue,
                self._stats_handler,
                self._mitm_mapper,
                self._db_wrapper,
                self._quest_gen,
                account_handler=self._account_handler,
                name="DataProc-%s" % str(i))
            # TODO: Own thread/loop?
            self._worker_threads.append(loop.create_task(data_processor.run()))
        if db_exec:
            db_exec.shutdown()

    async def shutdown(self):
        # TODO: Stop accepting data in the queue...
        if self._mitm_data_queue is not None:
            await self._mitm_data_queue.join()

        logger.info("Stopping {} MITM data processors", len(self._worker_threads))
        for worker_thread in self._worker_threads:
            worker_thread.cancel()
        logger.info("Stopped MITM data processors")
