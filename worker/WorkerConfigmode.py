import time
from threading import Event, Lock, Thread, current_thread

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
            time.sleep(1)

    def stop_worker(self):
        self._stop_worker_event.set()

    def set_geofix_sleeptime(self, sleeptime):
        return True
