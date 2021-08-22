import asyncio
import time

from mapadroid.db.helper.TrsStatusHelper import TrsStatusHelper
from mapadroid.worker.strategy.AbstractWorkerStrategy import AbstractWorkerStrategy
from loguru import logger


class NopStrategy(AbstractWorkerStrategy):
    async def _additional_health_check(self) -> None:
        pass

    async def pre_work_loop(self):
        logger.warning("Worker started in configmode! This is special, configuration only mode - do not expect"
                       " scans or avatar moving. After you are done with initial configuration remove -cm flag")
        await self._mapping_manager.register_worker_to_routemanager(self._area_id,
                                                                    self._worker_state.origin)
        logger.debug("Setting device to idle for routemanager")
        async with self._db_wrapper as session, session:
            await TrsStatusHelper.save_idle_status(session, self._db_wrapper.get_instance_id(),
                                                   self._worker_state.device_id, 0)
            await session.commit()

    async def health_check(self) -> bool:
        return True

    async def pre_location_update(self):
        return

    async def move_to_location(self):
        return int(time.time()), self._worker_state.current_location

    async def post_move_location_routine(self, timestamp):
        await asyncio.sleep(60)

    async def worker_specific_setup_start(self):
        pass

    async def worker_specific_setup_stop(self):
        pass