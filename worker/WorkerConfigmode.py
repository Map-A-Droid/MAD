import time
import math
from threading import Event

from utils.logging import logger
from websocket.communicator import Communicator
from utils.routeutil import check_walker_value_type
from utils.MappingManager import MappingManager


class WorkerConfigmode(object):
    def __init__(self, args, id, websocket_handler, walker, mapping_manager):
        self._communicator = Communicator(
            websocket_handler, id, self, args.websocket_command_timeout)
        self._stop_worker_event = Event()
        self._id = id
        self._walker = walker
        self.workerstart = None
        self._mapping_manager: MappingManager = mapping_manager

    def set_devicesettings_value(self, key: str, value):
        self._mapping_manager.set_devicesetting_value_of(self._id, key, value)

    def get_communicator(self):
        return self._communicator

    def start_worker(self):
        logger.info("Worker {} started in configmode", str(self._id))
        while not self._stop_worker_event.isSet() or self.check_walker():
            time.sleep(60)
        self.set_devicesettings_value('finished', True)
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

    def check_walker(self):
        mode = self._walker['walkertype']
        if mode == "countdown":
            logger.info("Checking walker mode 'countdown'")
            countdown = self._walker['walkervalue']
            if not countdown:
                logger.error(
                        "No Value for Mode - check your settings! Killing worker")
                return False
            if self.workerstart is None:
                self.workerstart = math.floor(time.time())
            else:
                if math.floor(time.time()) >= int(self.workerstart) + int(countdown):
                    return False
            return True
        elif mode == "timer":
            logger.debug("Checking walker mode 'timer'")
            exittime = self._walker['walkervalue']
            if not exittime or ':' not in exittime:
                logger.error(
                        "No or wrong Value for Mode - check your settings! Killing worker")
                return False
            return check_walker_value_type(exittime)
        elif mode == "round":
            logger.error("Rounds while sleep - HAHAHAH")
            return False
        elif mode == "period":
            logger.debug("Checking walker mode 'period'")
            period = self._walker['walkervalue']
            if len(period) == 0:
                logger.error(
                        "No Value for Mode - check your settings! Killing worker")
                return False
            return check_walker_value_type(period)
        elif mode == "coords":
            exittime = self._walker['walkervalue']
            if len(exittime) > 0:
                return check_walker_value_type(exittime)
            return True
        elif mode == "idle":
            logger.debug("Checking walker mode 'idle'")
            if len(self._walker['walkervalue']) == 0:
                logger.error(
                        "Wrong Value for mode - check your settings! Killing worker")
                return False
            sleeptime = self._walker['walkervalue']
            logger.info('{} going to sleep', str(self._id))
            killpogo = False
            if check_walker_value_type(sleeptime):
                self._stop_pogo()
                killpogo = True
            while not self._stop_worker_event.isSet() and check_walker_value_type(sleeptime):
                time.sleep(1)
            logger.info('{} just woke up', str(self._id))
            if killpogo:
                self._start_pogo()
            return False
        else:
            logger.error("Unknown walker mode! Killing worker")
            return False
