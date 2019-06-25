import time
from threading import Event

from utils.logging import logger
from websocket.communicator import Communicator


class WorkerConfigmode(object):
    def __init__(self, args, id, websocket_handler):
        self._communicator = Communicator(
            websocket_handler, id, self, args.websocket_command_timeout)
        self._stop_worker_event = Event()
        self._id = id

    def get_communicator(self):
        return self._communicator

    def start_worker(self):
        logger.info("Worker {} started in configmode", str(self._id))
        while not self._stop_worker_event.isSet():
            time.sleep(60)
        self._communicator.cleanup_websocket()
        logger.info("Internal cleanup of {} finished", str(self._id))

    def stop_worker(self):
        if self._stop_worker_event.set():
            logger.info('Worker {} already stopped - waiting for it', str(self._id))
        else:
            self._stop_worker_event.set()
            logger.warning("Worker {} stop called", str(self._id))

    def set_geofix_sleeptime(self, sleeptime):
        return True
