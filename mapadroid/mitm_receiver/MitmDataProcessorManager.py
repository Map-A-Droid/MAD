from multiprocessing import JoinableQueue

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.mitm_receiver.MitmMapper import MitmMapper
from mapadroid.mitm_receiver.SerializedMitmDataProcessor import SerializedMitmDataProcessor
from mapadroid.utils.logging import get_logger, LoggerEnums

logger = get_logger(LoggerEnums.mitm)


class MitmDataProcessorManager():
    def __init__(self, args, mitm_mapper: MitmMapper, db_wrapper: DbWrapper):
        self._worker_threads = []
        self._args = args
        self._mitm_data_queue: JoinableQueue = JoinableQueue()
        self._mitm_mapper: MitmMapper = mitm_mapper
        self._db_wrapper: DbWrapper = db_wrapper

    def get_queue(self):
        return self._mitm_data_queue

    def launch_processors(self):
        for i in range(self._args.mitmreceiver_data_workers):
            data_processor: SerializedMitmDataProcessor = SerializedMitmDataProcessor(
                self._mitm_data_queue,
                self._args,
                self._mitm_mapper,
                self._db_wrapper,
                name="SerialiedMitmDataProcessor-%s" % str(i))

            data_processor.start()
            self._worker_threads.append(data_processor)

    def shutdown(self):
        logger.info("Stopping {} MITM data processors", len(self._worker_threads))
        for worker_thread in self._worker_threads:
            worker_thread.terminate()
            worker_thread.join()
        logger.info("Stopped MITM datap rocessors")

        if self._mitm_data_queue is not None:
            self._mitm_data_queue.close()


