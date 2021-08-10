import asyncio
import time
from abc import ABC
from asyncio import Task
from typing import Dict

from loguru import logger

from mapadroid.data_handler.MitmMapper import MitmMapper
from mapadroid.db.helper.TrsStatusHelper import TrsStatusHelper
from mapadroid.mapping_manager import MappingManager
from mapadroid.mapping_manager.MappingManagerDevicemappingKey import MappingManagerDevicemappingKey
from mapadroid.ocr.pogoWindows import PogoWindows
from mapadroid.utils.madConstants import TIMESTAMP_NEVER
from mapadroid.utils.madGlobals import PositionType
from mapadroid.websocket.AbstractCommunicator import AbstractCommunicator
from mapadroid.worker.Worker import WorkerBase


class MITMBase(WorkerBase, ABC):
    def __init__(self, args, dev_id, origin, communicator: AbstractCommunicator,
                 mapping_manager: MappingManager,
                 area_id: int, routemanager_id: int, db_wrapper, mitm_mapper: MitmMapper,
                 pogo_window_manager: PogoWindows,
                 walker: Dict = None, event=None):
        WorkerBase.__init__(self, args, dev_id, origin, communicator,
                            mapping_manager=mapping_manager, area_id=area_id,
                            routemanager_id=routemanager_id,
                            db_wrapper=db_wrapper,
                            pogo_window_manager=pogo_window_manager, walker=walker, event=event)
        self._mitm_mapper = mitm_mapper

        self._current_sleep_time = 0
        self._clear_quests_failcount = 0
        self._dev_id = dev_id

    async def start_worker(self) -> Task:
        async with self._db_wrapper as session, session:
            try:
                await TrsStatusHelper.save_idle_status(session, self._db_wrapper.get_instance_id(),
                                                       self._dev_id, 0)
                await session.commit()
            except Exception as e:
                logger.warning("Failed saving idle status: {}", e)

        now_ts: int = int(time.time())
        await self._mitm_mapper.stats_collect_location_data(self._origin, self.current_location, True,
                                                            now_ts,
                                                            PositionType.STARTUP,
                                                            TIMESTAMP_NEVER,
                                                            self._walker.name, self._transporttype,
                                                            now_ts)


        return await super().start_worker()


    async def _close_gym(self, delayadd):
        logger.debug('{_close_gym} called')
        x, y = self._resocalc.get_close_main_button_coords(self)
        await self._communicator.click(int(x), int(y))
        await asyncio.sleep(1 + int(delayadd))
        logger.debug('{_close_gym} called')



    async def _worker_specific_setup_stop(self):
        logger.info("Stopping pogodroid")
        return await self._communicator.stop_app("com.mad.pogodroid")

    async def _worker_specific_setup_start(self):
        logger.info("Starting pogodroid")
        start_result = await self._communicator.start_app("com.mad.pogodroid")
        await asyncio.sleep(5)
        # won't work if PogoDroid is repackaged!
        await self._communicator.passthrough("am startservice com.mad.pogodroid/.services.HookReceiverService")
        return start_result
