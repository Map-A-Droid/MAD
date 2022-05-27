from typing import Optional, Tuple, List, Union

from mapadroid.data_handler.mitm_data.holder.latest_mitm_data.LatestMitmDataEntry import LatestMitmDataEntry
from mapadroid.utils.DatetimeWrapper import DatetimeWrapper
from mapadroid.utils.ProtoIdentifier import ProtoIdentifier
from mapadroid.utils.logging import LoggerEnums, get_logger
from mapadroid.utils.madGlobals import FortSearchResultTypes
from mapadroid.worker.ReceivedTypeEnum import ReceivedType
from mapadroid.worker.strategy.plain.AbstractWorkerMitmStrategy import AbstractWorkerMitmStrategy

logger = get_logger(LoggerEnums.worker)


class WorkerMonMitmStrategy(AbstractWorkerMitmStrategy):
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
            if await self._gmo_contains_wild_mons_closeby(latest_proto_data):
                data_found = latest_proto_data
                type_of_data_found = ReceivedType.GMO
            else:
                # TODO: If there is no spawnpoint with a valid timer, this results in timeouts during ordinary routes...
                logger.debug("Data looked for not in GMO")
        elif proto_to_wait_for == ProtoIdentifier.ENCOUNTER:
            data_found = latest_proto_data
            type_of_data_found = ReceivedType.MON

        return type_of_data_found, data_found

    async def post_move_location_routine(self, timestamp) -> Optional[Tuple[ReceivedType,
                                                                            Optional[
                                                                                Union[dict, FortSearchResultTypes]]]]:
        received = await super().post_move_location_routine(timestamp)
        if not received:
            return None
        type_received, data_gmo, time_received = received
        if data_gmo and await self._gmo_contains_mons_to_be_encountered(
                data_gmo):
            # Subtract a second as... encounters may overtake GMOs
            type_received, data, time_received = await self._wait_for_data(time_received - 1, ProtoIdentifier.ENCOUNTER, 5)
            if type_received != ReceivedType.MON:
                logger.warning("Worker failed to receive encounter data at {}, {}. Worker will continue with "
                               "the next location",
                               self._worker_state.current_location.lat,
                               self._worker_state.current_location.lng)
        return type_received, data_gmo

    async def _get_ids_iv_and_scanmode(self) -> Tuple[List[int], str]:
        scanmode = "mons"
        ids_iv = []
        routemanager_settings = await self._mapping_manager.routemanager_get_settings(self._area_id)
        if routemanager_settings is not None:
            ids_iv = self._mapping_manager.get_monlist(self._area_id)
        return ids_iv, scanmode
