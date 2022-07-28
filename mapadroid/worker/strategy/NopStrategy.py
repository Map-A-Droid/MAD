import asyncio
import time

from loguru import logger

from mapadroid.db.helper.TrsStatusHelper import TrsStatusHelper
from mapadroid.utils.collections import Location
from mapadroid.worker.strategy.AbstractWorkerStrategy import \
    AbstractWorkerStrategy


class NopStrategy(AbstractWorkerStrategy):
    async def _additional_health_check(self) -> None:
        pass

    async def pre_work_loop(self):
        logger.warning("Worker started in nop-mode! Do not expect"
                       " scans or avatar moving. If you have started MAD in configmode, this is normal behaviour. After you are done with initial configuration remove -cm flag")

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

    async def check_location_is_valid(self) -> bool:
        return True

    async def grab_next_location(self) -> None:
        await super().grab_next_location()
        if not self._worker_state.current_location:
            self._worker_state.current_location = Location(0.0, 0.0)
