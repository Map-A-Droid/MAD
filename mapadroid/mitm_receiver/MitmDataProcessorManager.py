import time
import threading
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
        self._queue_check_thread = None
        self._stop_queue_check_thread = False

        self._queue_check_thread = threading.Thread(target=self._queue_size_check, args=())
        self._queue_check_thread.daemon = True
        self._queue_check_thread.start()

    def get_queue(self):
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
        self._stop_queue_check_thread = True

        logger.info("Stopping {} MITM data processors", len(self._worker_threads))
        for worker_thread in self._worker_threads:
            worker_thread.terminate()
            worker_thread.join()
        logger.info("Stopped MITM data processors")

        if self._mitm_data_queue is not None:
            self._mitm_data_queue.close()
