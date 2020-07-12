import math
import time
from threading import Event
from typing import Optional

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.mitm_receiver.MitmMapper import MitmMapper
from mapadroid.utils import MappingManager
from mapadroid.utils.madGlobals import (
    WebsocketWorkerRemovedException,
    WebsocketWorkerTimeoutException,
    InternalStopWorkerException,
    WebsocketWorkerConnectionClosedException)
from mapadroid.utils.routeutil import check_walker_value_type
from mapadroid.websocket.AbstractCommunicator import AbstractCommunicator
from mapadroid.worker.AbstractWorker import AbstractWorker
from mapadroid.utils.logging import get_logger, LoggerEnums


logger = get_logger(LoggerEnums.worker)


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
        self.logger.info("Worker started in configmode")
        self._mapping_manager.register_worker_to_routemanager(self._routemanager_name, self._origin)
        self.logger.debug("Setting device to idle for routemanager")
        self._db_wrapper.save_idle_status(self._dev_id, True)
        self.logger.debug("Device set to idle for routemanager")
        while self.check_walker() and not self._stop_worker_event.is_set():
            if self._args.config_mode:
                time.sleep(10)
            else:
                position_type = self._mapping_manager.routemanager_get_position_type(self._routemanager_name,
                                                                                     self._origin)
                if position_type is None:
                    self.logger.warning("Mappings/Routemanagers have changed, stopping worker to be created again")
                    self._stop_worker_event.set()
                    time.sleep(1)
                else:
                    time.sleep(10)
        self.set_devicesettings_value('finished', True)
        self._mapping_manager.unregister_worker_from_routemanager(self._routemanager_name, self._origin)
        try:
            self._communicator.cleanup()
        finally:
            self.logger.info("Internal cleanup finished")
        return

    def stop_worker(self):
        if self._stop_worker_event.set():
            self.logger.info('Worker already stopped - waiting for it')
        else:
            self._stop_worker_event.set()
            self.logger.warning("Worker stop called")

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
        if walkereventid is None:
            walkereventid = 1
        if walkereventid != self._event.get_current_event_id():
            self.logger.warning("A other Event has started - leaving now")
            return False
        mode = self._walker['walkertype']
        if mode == "countdown":
            self.logger.info("Checking walker mode 'countdown'")
            countdown = self._walker['walkervalue']
            if not countdown:
                self.logger.error("No Value for Mode - check your settings! Killing worker")
                return False
            if self.workerstart is None:
                self.workerstart = math.floor(time.time())
            else:
                if math.floor(time.time()) >= int(self.workerstart) + int(countdown):
                    return False
            return True
        elif mode == "timer":
            self.logger.debug("Checking walker mode 'timer'")
            exittime = self._walker['walkervalue']
            if not exittime or ':' not in exittime:
                self.logger.error("No or wrong Value for Mode - check your settings! Killing worker")
                return False
            return check_walker_value_type(exittime)
        elif mode == "round":
            self.logger.error("Rounds while sleep - HAHAHAH")
            return False
        elif mode == "period":
            self.logger.debug("Checking walker mode 'period'")
            period = self._walker['walkervalue']
            if len(period) == 0:
                self.logger.error("No Value for Mode - check your settings! Killing worker")
                return False
            return check_walker_value_type(period)
        elif mode == "coords":
            exittime = self._walker['walkervalue']
            if len(exittime) > 0:
                return check_walker_value_type(exittime)
            return True
        elif mode == "idle":
            self.logger.debug("Checking walker mode 'idle'")
            if len(self._walker['walkervalue']) == 0:
                self.logger.error("Wrong Value for mode - check your settings! Killing worker")
                return False
            sleeptime = self._walker['walkervalue']
            self.logger.info('going to sleep')
            killpogo = False
            if check_walker_value_type(sleeptime):
                self._stop_pogo()
                killpogo = True
                self.logger.debug("Setting device to idle for routemanager")
                self._db_wrapper.save_idle_status(self._dev_id, True)
                self.logger.debug("Device set to idle for routemanager")
            while check_walker_value_type(sleeptime) and not self._stop_worker_event.isSet():
                time.sleep(1)
            self.logger.info('just woke up')
            if killpogo:
                try:
                    self._start_pogo()
                except (WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException,
                        WebsocketWorkerConnectionClosedException):
                    self.logger.error("Timeout during init")
            return False
        else:
            self.logger.error("Unknown walker mode! Killing worker")
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
            self.logger.warning("Turning screen on")
            self._communicator.turn_screen_on()
            time.sleep(self.get_devicesettings_value("post_turn_screen_on_delay", 7))

        while not pogo_topmost:
            self._mitm_mapper.set_injection_status(self._origin, False)
            self._communicator.start_app("com.nianticlabs.pokemongo")
            time.sleep(1)
            self._communicator.is_pogo_topmost()

        reached_raidtab = False
        self._wait_pogo_start_delay()

        return reached_raidtab

    def _wait_for_injection(self):
        self._not_injected_count = 0
        reboot = self.get_devicesettings_value('reboot', False)
        injection_thresh_reboot = 'Unlimited'
        if reboot:
            injection_thresh_reboot = int(self.get_devicesettings_value("injection_thresh_reboot", 20))
        while not self._mitm_mapper.get_injection_status(self._origin):
            if reboot and self._not_injected_count >= injection_thresh_reboot:
                self.logger.error("Nt get injected in time - reboot")
                self._reboot()
                return False
            self.logger.info("Didn't receive any data yet. (Retry count: {}/{})", str(self._not_injected_count),
                             str(injection_thresh_reboot))
            if self._stop_worker_event.isSet():
                self.logger.error("Killed while waiting for injection")
                return False
            self._not_injected_count += 1
            wait_time = 0
            while wait_time < 20:
                wait_time += 1
                if self._stop_worker_event.isSet():
                    self.logger.error("Worker get killed while waiting for injection")
                    return False
                time.sleep(1)
        return True

    def _reboot(self):
        if not self.get_devicesettings_value("reboot", True):
            self.logger.warning("Reboot command to be issued to device but reboot is disabled. Skipping reboot")
            return True
        try:
            start_result = self._communicator.reboot()
        except (WebsocketWorkerRemovedException, WebsocketWorkerConnectionClosedException):
            self.logger.error("Could not reboot due to client already having disconnected")
            start_result = False
        time.sleep(5)
        self._db_wrapper.save_last_reboot(self._dev_id)
        self.stop_worker()
        return start_result

    def _wait_pogo_start_delay(self):
        delay_count: int = 0
        pogo_start_delay: int = self.get_devicesettings_value("post_pogo_start_delay", 60)
        self.logger.info('Waiting for pogo start: {} seconds', pogo_start_delay)

        while delay_count <= pogo_start_delay:
            if self._stop_worker_event.is_set():
                self.logger.error("Killed while waiting for pogo start")
                raise InternalStopWorkerException
            time.sleep(1)
            delay_count += 1

    def trigger_check_research(self):
        # not on configmode
        return
