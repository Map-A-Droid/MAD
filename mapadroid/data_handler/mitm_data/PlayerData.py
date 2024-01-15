from typing import Dict, List, Optional, Union

from mapadroid.data_handler.AbstractWorkerHolder import AbstractWorkerHolder
from mapadroid.data_handler.mitm_data.holder.latest_mitm_data.LatestMitmDataEntry import \
    LatestMitmDataEntry
from mapadroid.data_handler.mitm_data.holder.latest_mitm_data.LatestMitmDataHolder import \
    LatestMitmDataHolder
from mapadroid.utils.ProtoIdentifier import ProtoIdentifier
from mapadroid.utils.collections import Location
from mapadroid.utils.logging import LoggerEnums, get_logger
import mapadroid.mitm_receiver.protos.Rpc_pb2 as pogoprotos

logger = get_logger(LoggerEnums.mitm_mapper)


class PlayerData(AbstractWorkerHolder):
    def __init__(self, origin: str):
        super().__init__(origin)
        self._level: int = 0
        self._poke_stop_visits: int = 0
        self._injected: bool = False
        self._latest_data_holder: LatestMitmDataHolder = LatestMitmDataHolder(self._worker)
        # Cell IDs seen in the last GMO to be able to tell when a GMO of a different location has been received
        self.__last_cell_ids: List = []
        # Timestamp when the GMO last contained different cell IDs than the GMO before that
        self.__last_possibly_moved: int = 0
        self.__last_known_location: Optional[Location] = None
        self.__quests_held: Optional[List[int]] = None

    # TODO: Move to MappingManager?
    async def set_injection_status(self, status: bool):
        self._injected = status

    async def get_injection_status(self) -> bool:
        return self._injected

    async def __set_level(self, level: int) -> None:
        if self._level != level:
            logger.info('set level {}', level)
            self._level = int(level)
        # TODO: Commit to DB

    async def get_level(self) -> int:
        return self._level

    async def __set_poke_stop_visits(self, visits: int) -> None:
        logger.debug2('set pokestops visited {}', visits)
        self._poke_stop_visits = visits
        # TODO: DB...

    async def get_poke_stop_visits(self) -> int:
        return self._poke_stop_visits

    def get_specific_latest_data(self, key: Union[int, str],
                                 timestamp_earliest: Optional[int] = None) -> Optional[LatestMitmDataEntry]:
        latest_entry: Optional[LatestMitmDataEntry] = self._latest_data_holder.get_latest(key)
        if not latest_entry or (timestamp_earliest and latest_entry.timestamp_of_data_retrieval
                                and int(timestamp_earliest) >= int(latest_entry.timestamp_of_data_retrieval)):
            return None
        else:
            return latest_entry

    def get_full_latest_data(self) -> Dict[Union[int, str], LatestMitmDataEntry]:
        return self._latest_data_holder.get_all()

    def update_latest(self, key: str, value: Union[List, Dict, bytes],
                      timestamp_received: Optional[int] = None,
                      timestamp_of_data_retrieval: Optional[int] = None,
                      location: Optional[Location] = None) -> None:
        self._latest_data_holder.update(key, value, timestamp_received, timestamp_of_data_retrieval, location)
        if key == str(ProtoIdentifier.GMO.value) and isinstance(value, bytes):
            gmo: pogoprotos.GetMapObjectsOutProto = pogoprotos.GetMapObjectsOutProto()
            gmo.ParseFromString(value)
            self.__parse_gmo_for_location(gmo, timestamp_received, location)
            self._injected = True

    # Async since we may move it to DB for persistence, same for above methods like level and
    # pokestops visited (today/week/total/whatever)
    async def get_last_possibly_moved(self) -> int:
        return self.__last_possibly_moved

    def __parse_gmo_for_location(self, gmo_payload: pogoprotos.GetMapObjectsOutProto, timestamp: int, location: Optional[Location]):
        if not gmo_payload.map_cell:
            return
        cell_ids: List[int] = [cell.s2_cell_id for cell in gmo_payload.map_cell]
        if not bool(set(cell_ids).intersection(self.__last_cell_ids)):
            self.__last_cell_ids = cell_ids
            self.__last_possibly_moved = timestamp
        if location:
            self.__last_known_location = location
        logger.debug4("Done __parse_gmo_for_location with {}", cell_ids)

    def get_last_known_location(self) -> Optional[Location]:
        return self.__last_known_location

    async def set_pokestop_visits(self, pokestop_visits: int) -> None:
        self._poke_stop_visits = pokestop_visits

    async def set_level(self, level: int) -> None:
        self._level = level

    async def set_quests_held(self, quests_held: Optional[List[int]]) -> None:
        self.__quests_held = quests_held

    async def get_quests_held(self) -> Optional[List[int]]:
        return self.__quests_held
