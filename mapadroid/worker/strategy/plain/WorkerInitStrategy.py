from enum import Enum
from typing import List, Optional, Tuple

from mapadroid.data_handler.mitm_data.holder.latest_mitm_data.LatestMitmDataEntry import \
    LatestMitmDataEntry
from mapadroid.db.model import SettingsAreaInitMitm
from mapadroid.utils.DatetimeWrapper import DatetimeWrapper
from mapadroid.utils.ProtoIdentifier import ProtoIdentifier
from mapadroid.utils.logging import LoggerEnums, get_logger
from mapadroid.worker.ReceivedTypeEnum import ReceivedType
from mapadroid.worker.strategy.plain.AbstractWorkerMitmStrategy import \
    AbstractWorkerMitmStrategy

logger = get_logger(LoggerEnums.worker)


class InitTypes(Enum):
    MONS = "mons"
    FORTS = "forts"


# Rural areas may not be populated with forts but wild or nearby mons...
keys_to_check_fort: List[str] = ["forts", "wild_pokemon", "nearby_pokemon"]


class WorkerInitStrategy(AbstractWorkerMitmStrategy):
    async def _check_for_data_content(self, latest: Optional[LatestMitmDataEntry],
                                      proto_to_wait_for: ProtoIdentifier,
                                      timestamp: int) -> Tuple[ReceivedType, Optional[object]]:
        type_of_data_found: ReceivedType = ReceivedType.UNDEFINED
        data_found: Optional[object] = None
        if not latest:
            return type_of_data_found, data_found
        # proto has previously been received, let's check the timestamp...
        timestamp_of_proto: int = latest.timestamp_of_data_retrieval
        logger.debug("Latest timestamp: {} vs. timestamp waited for: {} of proto {}",
                     DatetimeWrapper.fromtimestamp(timestamp_of_proto), DatetimeWrapper.fromtimestamp(timestamp),
                     proto_to_wait_for)
        if timestamp_of_proto < timestamp:
            logger.debug("latest timestamp of proto {} ({}) is older than {}", proto_to_wait_for,
                         timestamp_of_proto, timestamp)
            # TODO: timeout error instead of data_error_counter? Differentiate timeout vs missing data (the
            # TODO: latter indicates too high speeds for example
            return type_of_data_found, data_found

        latest_proto_data: dict = latest.data
        if latest_proto_data is None:
            return ReceivedType.UNDEFINED, data_found
        if proto_to_wait_for == ProtoIdentifier.GMO:
            area_settings: Optional[SettingsAreaInitMitm] = await self._mapping_manager.routemanager_get_settings(
                self._area_id)
            init_type: InitTypes = InitTypes(area_settings.init_type)
            if ((init_type == InitTypes.MONS
                 and await self._gmo_contains_wild_mons_closeby(latest_proto_data))
                    or (init_type == InitTypes.FORTS
                        and self._gmo_cells_contain_multiple_of_key(latest_proto_data, keys_to_check_fort))):
                data_found = latest_proto_data
                type_of_data_found = ReceivedType.GMO
            else:
                logger.debug("Data looked for not in GMO")
        elif proto_to_wait_for == ProtoIdentifier.ENCOUNTER:
            data_found = latest_proto_data
            type_of_data_found = ReceivedType.MON

        return type_of_data_found, data_found

    async def _get_ids_iv_and_scanmode(self) -> Tuple[List[int], str]:
        scanmode = "mons"
        ids_iv = []
        routemanager_settings = await self._mapping_manager.routemanager_get_settings(self._area_id)
        if routemanager_settings is not None:
            ids_iv = self._mapping_manager.get_monlist(self._area_id)
        return ids_iv, scanmode
