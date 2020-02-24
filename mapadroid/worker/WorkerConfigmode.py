import math
import time
from threading import Event
from typing import Optional

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.mitm_receiver.MitmMapper import MitmMapper
from mapadroid.utils import MappingManager
from mapadroid.utils.logging import logger
from mapadroid.utils.madGlobals import (
    WebsocketWorkerRemovedException,
    WebsocketWorkerTimeoutException,
    InternalStopWorkerException,
    WebsocketWorkerConnectionClosedException)
from mapadroid.utils.routeutil import check_walker_value_type
from mapadroid.websocket.AbstractCommunicator import AbstractCommunicator
from mapadroid.worker.AbstractWorker import AbstractWorker


class WorkerConfigmode(AbstractWorker):
    def __init__(self, args, dev_id, origin, communicator: AbstractCommunicator, walker, mapping_manager,
                 mitm_mapper: MitmMapper, db_wrapper: DbWrapper, area_id: int, routemanager_name: str, event):
        AbstractWorker.__init__(self, origin=origin, communicator=communicator)

        self._args = args
        self._event = event
        self._stop_worker_event = Event()
        self._dev_id = dev_id
        self._origin = origin
        self._routemanager_name = routemanager_name
        self._area_id = area_id
        self._walker = walker
        self.workerstart = None
        self._mapping_manager: MappingManager = mapping_manager
        self._mitm_mapper = mitm_mapper
        self._db_wrapper = db_wrapper

    def set_devicesettings_value(self, key: str, value):
        self._mapping_manager.set_devicesetting_value_of(self._origin, key, value)

    def get_devicesettings_value(self, key: str, default_value: object = None):
        devicemappings: Optional[dict] = self._mapping_manager.get_devicemappings_of(self._origin)
        if devicemappings is None:
            return default_value
        return devicemappings.get("settings", {}).get(key, default_value)

    def get_communicator(self):
        return self._communicator

    def start_worker(self):
        logger.info("Worker {} started in configmode", str(self._origin))
        self._mapping_manager.register_worker_to_routemanager(self._routemanager_name, self._origin)
        logger.debug("Setting device to idle for routemanager")
        self._db_wrapper.save_idle_status(self._dev_id, True)
        logger.debug("Device set to idle for routemanager {}", str(self._origin))
        while self.check_walker() and not self._stop_worker_event.is_set():
            position_type = self._mapping_manager.routemanager_get_position_type(self._routemanager_name,
                                                                                 self._origin)
            if position_type is None:
                logger.warning("Mappings/Routemanagers have changed, stopping worker to be created again")
                self._stop_worker_event.set()
                time.sleep(1)
            else:
                time.sleep(10)
        self.set_devicesettings_value('finished', True)
        self._mapping_manager.unregister_worker_from_routemanager(self._routemanager_name, self._origin)
        try:
            self._communicator.cleanup()
        finally:
            logger.info("Internal cleanup of {} finished", str(self._origin))
        return

    def stop_worker(self):
        if self._stop_worker_event.set():
            logger.info('Worker {} already stopped - waiting for it', str(self._origin))
        else:
            self._stop_worker_event.set()
            logger.warning("Worker {} stop called", str(self._origin))

    def is_stopping(self) -> bool:
        return self._stop_worker_event.is_set()

    def set_geofix_sleeptime(self, sleeptime: int):
        return True

    def set_job_activated(self):
        return True

    def set_job_deactivated(self):
        return True

    def check_walker(self):
        if self._walker is None:
            return True
        walkereventid = self._walker.get('eventid', None)
        if walkereventid is None: walkereventid = 1
        if walkereventid != self._event.get_current_event_id():
            logger.warning("A other Event has started - leaving now")
            return False
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
            logger.info('{} going to sleep', str(self._origin))
            killpogo = False
            if check_walker_value_type(sleeptime):
                self._stop_pogo()
                killpogo = True
                logger.debug("Setting device to idle for routemanager")
                self._db_wrapper.save_idle_status(self._dev_id, True)
                logger.debug("Device set to idle for routemanager {}", str(self._origin))
            while check_walker_value_type(sleeptime) and not self._stop_worker_event.isSet():
                time.sleep(1)
            logger.info('{} just woke up', str(self._origin))
            if killpogo:
                try:
                    self._start_pogo()
                except (WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException,
                        WebsocketWorkerConnectionClosedException):
                    logger.error("Timeout during init of worker {}", str(self._origin))
            return False
        else:
            logger.error("Unknown walker mode! Killing worker")
            return False

    def _stop_pogo(self):
        attempts = 0
        stop_result = self._communicator.stop_app("com.nianticlabs.pokemongo")
        pogoTopmost = self._communicator.is_pogo_topmost()
        while pogoTopmost:
            attempts += 1
            if attempts > 10:
                return False
            stop_result = self._communicator.stop_app(
                "com.nianticlabs.pokemongo")
            time.sleep(1)
            pogoTopmost = self._communicator.is_pogo_topmost()
        return stop_result

    def _start_pogo(self):
        pogo_topmost = self._communicator.is_pogo_topmost()
        if pogo_topmost:
            return True

        if not self._communicator.is_screen_on():
            self._communicator.start_app("de.grennith.rgc.remotegpscontroller")
            logger.warning("Turning screen on")
            self._communicator.turn_screen_on()
            time.sleep(self.get_devicesettings_value("post_turn_screen_on_delay", 7))

        start_result = False
        while not pogo_topmost:
            self._mitm_mapper.set_injection_status(self._origin, False)
            start_result = self._communicator.start_app(
                "com.nianticlabs.pokemongo")
            time.sleep(1)
            pogo_topmost = self._communicator.is_pogo_topmost()

        reached_raidtab = False
        self._wait_pogo_start_delay()

        return reached_raidtab

    def _wait_for_injection(self):
        self._not_injected_count = 0
        while not self._mitm_mapper.get_injection_status(self._origin):
            if self._not_injected_count >= 20:
                logger.error("Worker {} not get injected in time - reboot", str(self._origin))
                self._reboot()
                return False
            logger.info("PogoDroid on worker {} didn't connect yet. Probably not injected? (Count: {})",
                        str(self._origin), str(self._not_injected_count))
            if self._stop_worker_event.isSet():
                logger.error("Worker {} get killed while waiting for injection", str(self._origin))
                return False
            self._not_injected_count += 1
            wait_time = 0
            while wait_time < 20:
                wait_time += 1
                if self._stop_worker_event.isSet():
                    logger.error("Worker {} get killed while waiting for injection", str(self._origin))
                    return False
                time.sleep(1)
        return True

    def _reboot(self):
        if not self.get_devicesettings_value("reboot", True):
            logger.warning("Reboot command to be issued to device but reboot is disabled. Skipping reboot")
            return True
        try:
            start_result = self._communicator.reboot()
        except (WebsocketWorkerRemovedException, WebsocketWorkerConnectionClosedException):
            logger.error(
                "Could not reboot due to client already having disconnected")
            start_result = False
        time.sleep(5)
        self._db_wrapper.save_last_reboot(self._dev_id)
        self.stop_worker()
        return start_result

    def _wait_pogo_start_delay(self):
        delay_count: int = 0
        pogo_start_delay: int = self.get_devicesettings_value("post_pogo_start_delay", 60)
        logger.info('Waiting for pogo start: {} seconds', str(pogo_start_delay))

        while delay_count <= pogo_start_delay:
            if self._stop_worker_event.is_set():
                logger.error("Worker {} get killed while waiting for pogo start", str(self._origin))
                raise InternalStopWorkerException
            time.sleep(1)
            delay_count += 1

    def trigger_check_research(self):
        # not on configmode
        return
