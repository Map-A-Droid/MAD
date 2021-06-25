import asyncio
import math
import time
from typing import Optional, Any

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.model import SettingsWalkerarea
from mapadroid.mitm_receiver.MitmMapper import MitmMapper
from mapadroid.mapping_manager import MappingManager
from mapadroid.mapping_manager.MappingManagerDevicemappingKey import MappingManagerDevicemappingKey
from mapadroid.utils.madGlobals import (
    InternalStopWorkerException, WebsocketWorkerConnectionClosedException,
    WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException)
from mapadroid.utils.routeutil import check_walker_value_type
from mapadroid.websocket.AbstractCommunicator import AbstractCommunicator
from mapadroid.worker.AbstractWorker import AbstractWorker
from loguru import logger


class WorkerConfigmode(AbstractWorker):
    def __init__(self, args, dev_id, origin, communicator: AbstractCommunicator, walker: SettingsWalkerarea,
                 mapping_manager: MappingManager,
                 mitm_mapper: MitmMapper, db_wrapper: DbWrapper, area_id: int, routemanager_id: int, event):
        AbstractWorker.__init__(self, origin=origin, communicator=communicator)
        self._args = args
        self._event = event
        self._stop_worker_event = asyncio.Event()
        self._dev_id = dev_id
        self._origin = origin
        self._routemanager_id = routemanager_id
        self._area_id = area_id
        self._walker = walker
        self.workerstart = None
        self._mapping_manager: MappingManager = mapping_manager
        self._mitm_mapper = mitm_mapper
        self._db_wrapper = db_wrapper


    async def set_devicesettings_value(self, key: MappingManagerDevicemappingKey, value: Optional[Any]):
        await self._mapping_manager.set_devicesetting_value_of(self._origin, key, value)

    async def get_devicesettings_value(self, key: MappingManagerDevicemappingKey, default_value: Optional[Any] = None):
        devicemappings: Optional[dict] = await self._mapping_manager.get_devicemappings_of(self._origin)
        if devicemappings is None:
            return default_value
        return devicemappings.get("settings", {}).get(key, default_value)

    async def start_worker(self):
        logger.warning("Worker started in configmode! This is special, configuration only mode - do not expect"
                            " scans or avatar moving. After you are done with initial configuration remove -cm flag")
        await self._mapping_manager.register_worker_to_routemanager(self._routemanager_id, self._origin)
        logger.debug("Setting device to idle for routemanager")
        await self._db_wrapper.save_idle_status(self._dev_id, True)
        logger.debug("Device set to idle for routemanager")
        while not self._stop_worker_event.is_set() and await self.check_walker():
            await asyncio.sleep(10)
        await self.set_devicesettings_value(MappingManagerDevicemappingKey.FINISHED, True)
        await self._mapping_manager.unregister_worker_from_routemanager(self._routemanager_id, self._origin)
        try:
            await self._communicator.cleanup()
        finally:
            logger.info("Internal cleanup finished")

    async def stop_worker(self):
        if self._stop_worker_event.set():
            logger.info('Worker already stopped - waiting for it')
        else:
            self._stop_worker_event.set()
            logger.warning("Worker stop called")

    def is_stopping(self) -> bool:
        return self._stop_worker_event.is_set()

    def set_geofix_sleeptime(self, sleeptime: int):
        return True

    def set_job_activated(self):
        return True

    def set_job_deactivated(self):
        return True

    async def check_walker(self):
        if self._walker is None:
            return True
        walkereventid = self._walker.get('eventid', None)
        if walkereventid is None:
            walkereventid = 1
        if walkereventid != self._event.get_current_event_id():
            logger.info("Another Event has started - leaving now")
            return False
        mode = self._walker['walkertype']
        if mode == "countdown":
            logger.info("Checking walker mode 'countdown'")
            countdown = self._walker['walkervalue']
            if not countdown:
                logger.error("No Value for Mode - check your settings! Killing worker")
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
                logger.error("No or wrong Value for Mode - check your settings! Killing worker")
                return False
            return check_walker_value_type(exittime)
        elif mode == "round":
            logger.warning("Rounds while sleep - HAHAHAH")
            return False
        elif mode == "period":
            logger.debug("Checking walker mode 'period'")
            period = self._walker['walkervalue']
            if len(period) == 0:
                logger.error("No Value for Mode - check your settings! Killing worker")
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
                logger.error("Wrong Value for mode - check your settings! Killing worker")
                return False
            sleeptime = self._walker['walkervalue']
            logger.info('going to sleep')
            killpogo = False
            if check_walker_value_type(sleeptime):
                await self._stop_pogo()
                killpogo = True
                logger.debug("Setting device to idle for routemanager")
                await self._db_wrapper.save_idle_status(self._dev_id, True)
                logger.debug("Device set to idle for routemanager")
            while check_walker_value_type(sleeptime) and not self._stop_worker_event.is_set():
                await asyncio.sleep(1)
            logger.info('just woke up')
            if killpogo:
                try:
                    await self._start_pogo()
                except (WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException,
                        WebsocketWorkerConnectionClosedException):
                    logger.error("Timeout during init")
            return False
        else:
            logger.error("Unknown walker mode! Killing worker")
            return False

    async def _stop_pogo(self):
        attempts = 0
        stop_result = await self._communicator.stop_app("com.nianticlabs.pokemongo")
        pogo_topmost = await self._communicator.is_pogo_topmost()
        while pogo_topmost:
            attempts += 1
            if attempts > 10:
                return False
            stop_result = await self._communicator.stop_app("com.nianticlabs.pokemongo")
            await asyncio.sleep(1)
            pogo_topmost = await self._communicator.is_pogo_topmost()
        return stop_result

    async def _start_pogo(self):
        pogo_topmost = await self._communicator.is_pogo_topmost()
        if pogo_topmost:
            return True

        if not await self._communicator.is_screen_on():
            await self._communicator.start_app("de.grennith.rgc.remotegpscontroller")
            logger.info("Turning screen on")
            await self._communicator.turn_screen_on()
            await asyncio.sleep(await self.get_devicesettings_value(MappingManagerDevicemappingKey.POST_TURN_SCREEN_ON_DELAY, 7))

        while not pogo_topmost:
            await self._mitm_mapper.set_injection_status(self._origin, False)
            await self._communicator.start_app("com.nianticlabs.pokemongo")
            await asyncio.sleep(1)
            pogo_topmost = await self._communicator.is_pogo_topmost()

        reached_raidtab = False
        await self._wait_pogo_start_delay()

        return reached_raidtab

    async def _wait_for_injection(self):
        self._not_injected_count = 0
        reboot = await self.get_devicesettings_value(MappingManagerDevicemappingKey.REBOOT, True)
        injection_thresh_reboot = 'Unlimited'
        if reboot:
            injection_thresh_reboot = int(await self.get_devicesettings_value(MappingManagerDevicemappingKey.INJECTION_THRESH_REBOOT, 20))
        while not await self._mitm_mapper.get_injection_status(self._origin):
            if reboot and self._not_injected_count >= injection_thresh_reboot:
                logger.error("Not injected in time - reboot")
                await self._reboot()
                return False
            logger.info("Didn't receive any data yet. (Retry count: {}/{})", str(self._not_injected_count),
                             str(injection_thresh_reboot))
            if self._stop_worker_event.is_set():
                logger.error("Killed while waiting for injection")
                return False
            self._not_injected_count += 1
            wait_time = 0
            while wait_time < 20:
                wait_time += 1
                if self._stop_worker_event.is_set():
                    logger.error("Worker get killed while waiting for injection")
                    return False
                await asyncio.sleep(1)
        return True

    async def _reboot(self):
        if not await self.get_devicesettings_value(MappingManagerDevicemappingKey.REBOOT, True):
            logger.warning("Reboot command to be issued to device but reboot is disabled. Skipping reboot")
            return True
        try:
            start_result = await self._communicator.reboot()
        except (WebsocketWorkerRemovedException, WebsocketWorkerConnectionClosedException):
            logger.warning("Could not reboot due to client already having disconnected")
            start_result = False
        await asyncio.sleep(5)
        await self._db_wrapper.save_last_reboot(self._dev_id)
        await self.stop_worker()
        return start_result

    async def _wait_pogo_start_delay(self):
        delay_count: int = 0
        pogo_start_delay: int = await self.get_devicesettings_value(MappingManagerDevicemappingKey.POST_POGO_START_DELAY, 60)
        logger.info('Waiting for pogo start: {} seconds', pogo_start_delay)

        while delay_count <= pogo_start_delay:
            if self._stop_worker_event.is_set():
                logger.error("Killed while waiting for pogo start")
                raise InternalStopWorkerException
            await asyncio.sleep(1)
            delay_count += 1
