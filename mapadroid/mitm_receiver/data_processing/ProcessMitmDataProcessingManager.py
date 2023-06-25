import asyncio
import multiprocessing
from asyncio import Task
from typing import List, Optional

from mapadroid.data_handler.mitm_data import AbstractMitmMapper
from mapadroid.data_handler.stats import AbstractStatsHandler
from mapadroid.db import DbWrapper
from mapadroid.mitm_receiver.data_processing.AbstractMitmDataProcessingManager import \
    AbstractMitmDataProcessingManager
from mapadroid.mitm_receiver.data_processing.InProcessMitmDataProcessorManager import \
    InProcessMitmDataProcessorManager
from mapadroid.utils.madGlobals import MadGlobals
from mapadroid.utils.questGen import QuestGen


class ProcessMitmDataProcessingManager(AbstractMitmDataProcessingManager):
    """
    In order to utilize as many cores as possible properly, a mitm data processing asyncio loop needs to be started for
     each core available.
     This class handles the creation of processes accordingly.
    """
    _data_queue: multiprocessing.Queue
    _db_wrapper: Optional[DbWrapper]
    _worker_threads: List[Task]
    _mitm_mapper: AbstractMitmMapper
    _stats_handler: AbstractStatsHandler
    _quest_gen: QuestGen
    _all_queues_of_processors: List[asyncio.Queue]

    def __init__(self):
        super().__init__()
        self._all_queues_of_processors = []

    async def launch_processors(self):
        for i in range(MadGlobals.application_args.mitmreceiver_data_workers):
            # As this loop starts processes, shared asyncio queues are not possible and need to be created and filled
            #  by this manager.

            data_processor: InProcessMitmDataProcessorManager = InProcessMitmDataProcessorManager(
                queue_of_task,
                self._mitm_mapper,
                self._db_wrapper,
                self._quest_gen,
                name="SerialiedMitmDataProcessor-%s" % str(i))

            data_processor.start()
            self._worker_threads.append(data_processor)
