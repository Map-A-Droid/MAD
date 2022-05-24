import asyncio
from typing import Optional, Union, List

from mapadroid.data_handler.mitm_data.AbstractMitmMapper import AbstractMitmMapper
from mapadroid.data_handler.mitm_data.MitmDataHandler import MitmDataHandler
from mapadroid.data_handler.mitm_data.holder.latest_mitm_data.LatestMitmDataEntry import LatestMitmDataEntry
from mapadroid.utils.collections import Location


class MitmMapper(AbstractMitmMapper):
    def __init__(self):
        self._mitm_data_handler: MitmDataHandler = MitmDataHandler()

    # ##
    # Data related methods
    # ##
    async def get_last_possibly_moved(self, worker: str) -> int:
        return await self._mitm_data_handler.get_last_possibly_moved(worker)

    async def update_latest(self, worker: str, key: str, value: Union[list, dict], timestamp_received_raw: float = None,
                            timestamp_received_receiver: float = None, location: Location = None) -> None:
        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, self._mitm_data_handler.update_latest, worker, key, value, timestamp_received_raw,
                             timestamp_received_receiver, location)

    async def request_latest(self, worker: str, key: str,
                             timestamp_earliest: Optional[int] = None) -> Optional[LatestMitmDataEntry]:
        return self._mitm_data_handler.request_latest(worker, key, timestamp_earliest)

    async def get_poke_stop_visits(self, worker: str) -> int:
        return await self._mitm_data_handler.get_poke_stop_visits(worker)

    async def get_level(self, worker: str) -> int:
        return await self._mitm_data_handler.get_level(worker)

    async def get_injection_status(self, worker: str) -> bool:
        return await self._mitm_data_handler.get_injection_status(worker)

    async def set_injection_status(self, worker: str, status: bool) -> None:
        await self._mitm_data_handler.set_injection_status(worker, status)

    async def get_last_known_location(self, worker: str) -> Optional[Location]:
        return self._mitm_data_handler.get_last_known_location(worker)

    async def set_level(self, worker: str, level: int) -> None:
        await self._mitm_data_handler.set_level(worker, level)

    async def set_pokestop_visits(self, worker: str, pokestop_visits: int) -> None:
        await self._mitm_data_handler.set_pokestop_visits(worker, pokestop_visits)

    async def set_quests_held(self, worker: str, quests_held: Optional[List[int]]) -> None:
        await self._mitm_data_handler.set_quests_held(worker, quests_held)

    async def get_quests_held(self, worker: str) -> Optional[List[int]]:
        return await self._mitm_data_handler.get_quests_held(worker)
