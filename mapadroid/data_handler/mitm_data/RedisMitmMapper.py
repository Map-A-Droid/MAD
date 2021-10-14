import time
from typing import Optional, List, Dict, Union

import ujson
from aioredis import Redis

from mapadroid.data_handler.mitm_data.AbstractMitmMapper import AbstractMitmMapper
from mapadroid.data_handler.mitm_data.holder.latest_mitm_data.LatestMitmDataEntry import LatestMitmDataEntry
from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.utils.ProtoIdentifier import ProtoIdentifier
from mapadroid.utils.collections import Location
from loguru import logger


class RedisMitmMapper(AbstractMitmMapper):
    LAST_POSSIBLY_MOVED_KEY = "last_possibly_moved:{}"
    # latest_data:{worker}:{data_key}
    LATEST_DATA_KEY = "latest_data:{}:{}"
    # latest_data:{worker}
    LAST_KNOWN_LOCATION_KEY = "last_known_location:{}"
    # injected:{worker}
    IS_INJECTED_KEY = "is_injected:{}"
    # last_cell_ids:{worker}
    LAST_CELL_IDS_KEY = "last_cell_ids:{}"
    # pokestops_visited:{worker}
    POKESTOPS_VISITED_KEY = "pokestops_visited:{}"
    # level:{worker}
    LEVEL_KEY = "level:{}"

    def __init__(self, db_wrapper: DbWrapper):
        self.__db_wrapper: DbWrapper = db_wrapper
        self.__cache: Optional[Redis] = None

    async def start(self):
        self.__cache: Redis = await self.__db_wrapper.get_cache()

    # ##
    # Data related methods
    # ##
    async def get_last_possibly_moved(self, worker: str) -> int:
        last_moved: Optional[int] = await self.__cache.get(RedisMitmMapper.LAST_POSSIBLY_MOVED_KEY.format(worker))
        return int(last_moved) if last_moved else 0

    async def update_latest(self, worker: str, key: str, value: Union[list, dict], timestamp_received_raw: float = None,
                            timestamp_received_receiver: float = None, location: Location = None) -> None:
        if timestamp_received_raw is None:
            timestamp_received_raw = int(time.time())
        if timestamp_received_receiver is None:
            timestamp_received_receiver = int(time.time())
        latest_entry: Optional[LatestMitmDataEntry] = await self.request_latest(worker, key)
        if (latest_entry and latest_entry.timestamp_received
                and (not timestamp_received_receiver
                     or latest_entry.timestamp_of_data_retrieval > timestamp_received_receiver)):
            # Ignore update as it yields an older timestamp than the one known to us
            return
        else:
            mitm_data_entry: LatestMitmDataEntry = LatestMitmDataEntry(location, timestamp_received_raw,
                                                                       timestamp_received_receiver, value)
            json_data = await mitm_data_entry.to_json()
            try:
                await self.__cache.set(RedisMitmMapper.LATEST_DATA_KEY.format(worker, key), json_data)
            except Exception as e:
                logger.exception(e)
        if key == str(ProtoIdentifier.GMO.value):
            await self.__parse_gmo_for_location(worker, value, timestamp_received_raw, location)
            await self.__cache.set(RedisMitmMapper.IS_INJECTED_KEY.format(worker), 1)

    async def __parse_gmo_for_location(self, worker: str, gmo_payload: Dict, timestamp: int, location: Optional[Location]):
        cells = gmo_payload.get("cells", None)
        if not cells:
            return
        cell_ids: List[int] = [cell['id'] for cell in cells]
        last_cell_ids_raw: Optional[str] = await self.__cache.get(RedisMitmMapper.LAST_CELL_IDS_KEY.format(worker))
        last_cell_ids: List[int] = []
        if last_cell_ids_raw:
            last_cell_ids: List[int] = ujson.loads(last_cell_ids_raw)
        if not bool(set(cell_ids).intersection(set(last_cell_ids))):
            await self.__cache.set(RedisMitmMapper.LAST_CELL_IDS_KEY.format(worker), ujson.dumps(cell_ids))
            await self.__cache.set(RedisMitmMapper.LAST_POSSIBLY_MOVED_KEY.format(worker), timestamp)
        if location:
            await self.__cache.set(RedisMitmMapper.LAST_KNOWN_LOCATION_KEY.format(worker), location.to_json())

    async def request_latest(self, worker: str, key: str,
                             timestamp_earliest: Optional[int] = None) -> Optional[LatestMitmDataEntry]:
        latest_data: Optional[str] = await self.__cache.get(RedisMitmMapper.LATEST_DATA_KEY.format(worker, key))
        if not latest_data:
            return None
        latest_entry: Optional[LatestMitmDataEntry] = await LatestMitmDataEntry.from_json(latest_data)
        if not latest_entry or (timestamp_earliest and latest_entry.timestamp_of_data_retrieval
                                and timestamp_earliest > latest_entry.timestamp_of_data_retrieval):
            return None
        else:
            return latest_entry

    async def get_poke_stop_visits(self, worker: str) -> int:
        pokestops_visited: Optional[int] = await self.__cache.get(RedisMitmMapper.POKESTOPS_VISITED_KEY.format(worker))
        return int(pokestops_visited) if pokestops_visited else 0

    async def get_level(self, worker: str) -> int:
        level: Optional[int] = await self.__cache.get(RedisMitmMapper.LEVEL_KEY.format(worker))
        return int(level) if level else 0

    async def get_injection_status(self, worker: str) -> bool:
        is_injected: Optional[bytes] = await self.__cache.get(RedisMitmMapper.IS_INJECTED_KEY.format(worker))
        return is_injected and int(is_injected) == 1

    async def set_injection_status(self, worker: str, status: bool) -> None:
        await self.__cache.set(RedisMitmMapper.IS_INJECTED_KEY.format(worker), 1 if status else 0)

    async def get_last_known_location(self, worker: str) -> Optional[Location]:
        last_known_location_raw: Optional[str] = await self.__cache.get(
            RedisMitmMapper.LAST_KNOWN_LOCATION_KEY.format(worker))
        if not last_known_location_raw:
            return None
        try:
            last_known_location: Location = Location.from_json(last_known_location_raw)
        except KeyError as e:
            return None
        return last_known_location

    async def set_level(self, worker: str, level: int) -> None:
        await self.__cache.set(RedisMitmMapper.LEVEL_KEY.format(worker), level)

    async def set_pokestop_visits(self, worker: str, pokestop_visits: int) -> None:
        await self.__cache.set(RedisMitmMapper.POKESTOPS_VISITED_KEY.format(worker), pokestop_visits)
