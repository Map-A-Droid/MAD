import time
from typing import Dict, Any, Optional

from mapadroid.data_handler.mitm_data.PlayerData import PlayerData
from mapadroid.data_handler.mitm_data.holder.latest_mitm_data.LatestMitmDataEntry import LatestMitmDataEntry
from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.utils.collections import Location
from loguru import logger


class MitmDataHandler:
    """
    Class storing the last received proto of an origin and other relevant data that has to be available asap
    """

    def __init__(self, db_wrapper: DbWrapper, application_args):
        self.__application_args = application_args
        self.__db_wrapper = db_wrapper
        self.__worker_data: Dict[str, PlayerData] = {}

    def __ensure_worker_data(self, worker: str) -> PlayerData:
        if worker not in self.__worker_data:
            self.__worker_data[worker] = PlayerData(worker, self.__application_args)
        return self.__worker_data[worker]

    async def set_injection_status(self, worker: str, status: bool) -> None:
        player_data: PlayerData = self.__ensure_worker_data(worker)
        await player_data.set_injection_status(status)

    async def get_injection_status(self, worker: str) -> bool:
        player_data: PlayerData = self.__ensure_worker_data(worker)
        return await player_data.get_injection_status()

    async def get_level(self, worker: str) -> int:
        player_data: PlayerData = self.__ensure_worker_data(worker)
        return await player_data.get_level()

    async def get_poke_stop_visits(self, worker: str) -> int:
        player_data: PlayerData = self.__ensure_worker_data(worker)
        return await player_data.get_poke_stop_visits()

    async def handle_inventory_data(self, worker: str, inventory_proto: dict) -> None:
        player_data: PlayerData = self.__ensure_worker_data(worker)
        await player_data.handle_inventory_data(inventory_proto)

    def request_latest(self, worker: str, key: str) -> Optional[LatestMitmDataEntry]:
        player_data: PlayerData = self.__ensure_worker_data(worker)
        logger.debug2("Request latest called")
        return player_data.get_specific_latest_data(key)

    def get_full_latest_data(self, worker: str) -> Dict[str, LatestMitmDataEntry]:
        player_data: PlayerData = self.__ensure_worker_data(worker)
        logger.debug2("Request full latest called")
        return player_data.get_full_latest_data()

    def update_latest(self, worker: str, key: str, value: Any, timestamp_received_raw: float = None,
                            timestamp_received_receiver: float = None, location: Location = None) -> None:
        player_data: PlayerData = self.__ensure_worker_data(worker)
        if timestamp_received_raw is None:
            timestamp_received_raw = int(time.time())

        if timestamp_received_receiver is None:
            timestamp_received_receiver = int(time.time())

        player_data.update_latest(key, value, timestamp_received_raw, timestamp_received_receiver, location)

    async def get_last_possibly_moved(self, worker: str) -> int:
        player_data: PlayerData = self.__ensure_worker_data(worker)
        return await player_data.get_last_possibly_moved()

    def get_last_known_location(self, worker) -> Optional[Location]:
        player_data: PlayerData = self.__ensure_worker_data(worker)
        return player_data.get_last_known_location()
