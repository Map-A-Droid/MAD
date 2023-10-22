import asyncio
from typing import Dict, List, Optional, Union

from aiocache import cached
from google.protobuf import json_format
from grpc.aio import AioRpcError
from loguru import logger

from mapadroid.data_handler.mitm_data.AbstractMitmMapper import \
    AbstractMitmMapper
from mapadroid.data_handler.mitm_data.holder.latest_mitm_data.LatestMitmDataEntry import \
    LatestMitmDataEntry
from mapadroid.grpc.compiled.mitm_mapper import mitm_mapper_pb2
from mapadroid.grpc.compiled.mitm_mapper.mitm_mapper_pb2 import (
    GetQuestsHeldResponse, InjectedRequest, InjectionStatus,
    LastKnownLocationResponse, LastMoved, LatestMitmDataEntryRequest,
    LatestMitmDataEntryResponse, LevelResponse, PokestopVisitsResponse,
    SetLevelRequest, SetPokestopVisitsRequest, SetQuestsHeldRequest)
from mapadroid.grpc.compiled.shared.Worker_pb2 import Worker
from mapadroid.grpc.stubs.mitm_mapper.mitm_mapper_pb2_grpc import \
    MitmMapperStub
from mapadroid.utils.collections import Location


class MitmMapperClient(MitmMapperStub, AbstractMitmMapper):
    def __init__(self, channel):
        super().__init__(channel)
        self._level_cache: Dict[str, int] = {}
        self._pokestop_visits_cache: Dict[str, int] = {}

    # Cache the update parameters to not spam it...
    @cached(ttl=30)
    async def set_level(self, worker: str, level: int) -> None:
        if self._level_cache.get(worker, 0) == level:
            return
        else:
            self._level_cache[worker] = level
        logger.debug("Submitting level {}", level)
        request: SetLevelRequest = SetLevelRequest()
        request.worker.name = worker
        request.level = level
        try:
            await self.SetLevel(request)
        except AioRpcError as e:
            logger.warning("Failed submitting level {}", e)

    @cached(ttl=60)
    async def set_pokestop_visits(self, worker: str, pokestop_visits: int) -> None:
        if self._pokestop_visits_cache.get(worker, 0) == pokestop_visits:
            return
        else:
            self._pokestop_visits_cache[worker] = pokestop_visits
        logger.debug("Submitting stops visited {}", pokestop_visits)
        request: SetPokestopVisitsRequest = SetPokestopVisitsRequest()
        request.worker.name = worker
        request.pokestop_visits = pokestop_visits
        try:
            await self.SetPokestopVisits(request)
        except AioRpcError as e:
            logger.warning("Failed submitting pokestop visits {}", e)

    async def get_last_possibly_moved(self, worker: str) -> int:
        try:
            response: LastMoved = await self.GetLastPossiblyMoved(name=worker)
            return response.timestamp
        except AioRpcError as e:
            logger.warning("Failed requesting last possibly moved {}", e)
            # TODO: Return time.time() to continue scans or throw a custom exception that needs to be handled?
            return 0

    async def update_latest(self, worker: str, key: str, value: Union[List, Dict, bytes],
                            timestamp_received_raw: float = None,
                            timestamp_received_receiver: float = None, location: Location = None) -> None:
        request: mitm_mapper_pb2.LatestMitmDataEntryUpdateRequest = mitm_mapper_pb2.LatestMitmDataEntryUpdateRequest()
        # TODO: Threaded transformation?
        request.worker.name = worker
        request.key = str(key)
        if location:
            request.data.location.latitude = location.lat
            request.data.location.longitude = location.lng
        if timestamp_received_raw:
            request.data.timestamp_received = int(timestamp_received_raw)
        if timestamp_received_receiver:
            request.data.timestamp_of_data_retrieval = int(timestamp_received_receiver)
        if isinstance(value, list):
            request.data.some_list.extend(value)
        elif isinstance(value, dict):
            request.data.some_dictionary.update(value)
        elif isinstance(value, bytes):
            request.data.raw_message = value
        else:
            raise ValueError("Cannot handle data")
        try:
            await self.UpdateLatest(request)
        except AioRpcError as e:
            logger.warning("Failed submitting latest data {}", e)

    async def request_latest(self, worker: str, key: str,
                             timestamp_earliest: Optional[int] = None) -> Optional[LatestMitmDataEntry]:
        request = LatestMitmDataEntryRequest()
        request.worker.name = worker
        request.key = str(key)
        if timestamp_earliest:
            request.timestamp_earliest = timestamp_earliest
        try:
            response: LatestMitmDataEntryResponse = await self.RequestLatest(request)
        except AioRpcError as e:
            logger.warning("Failed requesting latest data {}", e)
            # TODO: Throw custom exception?
            return None
        if not response.HasField("entry"):
            return None
        loop = asyncio.get_running_loop()
        latest: LatestMitmDataEntry = await loop.run_in_executor(
            None, self.__transform_proto_data_entry, response.entry)
        return latest

    def __transform_proto_data_entry(self, entry: mitm_mapper_pb2.LatestMitmDataEntry) -> LatestMitmDataEntry:
        location: Optional[Location] = None
        if entry.location:
            location: Location = Location(entry.location.latitude, entry.location.longitude)

        if entry.HasField(
                "some_dictionary"):
            data = entry.some_dictionary
        elif entry.HasField(
                "some_list"):
            data = entry.some_list
        else:
            data = None
        if data:
            formatted = json_format.MessageToDict(data)
        else:
            formatted = None
        entry: LatestMitmDataEntry = LatestMitmDataEntry(location=location,
                                                         timestamp_received=entry.timestamp_received,
                                                         timestamp_of_data_retrieval=entry.timestamp_of_data_retrieval,
                                                         data=formatted)
        return entry

    @cached(ttl=30)
    async def get_poke_stop_visits(self, worker: str) -> int:
        request: Worker = Worker()
        request.name = worker
        try:
            response: PokestopVisitsResponse = await self.GetPokestopVisits(request)
            return response.stops_visited
        except AioRpcError as e:
            logger.warning("Failed requesting pokestop visits {}", e)
            # TODO: Custom Exception
            return self._pokestop_visits_cache.get(worker, 0)

    @cached(ttl=60)
    async def get_level(self, worker: str) -> int:
        request: Worker = Worker()
        request.name = worker
        try:
            response: LevelResponse = await self.GetLevel(request)
            return response.level
        except AioRpcError as e:
            logger.warning("Failed requesting level {}", e)
            # TODO: Custom Exception
            return self._level_cache.get(worker, 0)

    async def get_injection_status(self, worker: str) -> bool:
        request: Worker = Worker()
        request.name = worker
        try:
            response: InjectionStatus = await self.GetInjectionStatus(request)
            return response.is_injected
        except AioRpcError as e:
            logger.warning("Failed submitting injection status {}", e)
            # TODO: Custom exception
            return False

    async def set_injection_status(self, worker: str, status: bool) -> None:
        request: InjectedRequest = InjectedRequest()
        request.worker.name = worker
        request.injected.is_injected = status
        try:
            await self.SetInjected(request)
        except AioRpcError as e:
            logger.warning("Failed setting injection status {}", e)
            # TODO: Custom exception?
            return

    async def get_last_known_location(self, worker: str) -> Optional[Location]:
        request: Worker = Worker()
        request.name = worker
        try:
            response: LastKnownLocationResponse = await self.GetLastKnownLocation(request)
        except AioRpcError as e:
            logger.warning("Failed requesting last known location {}", e)
            # TODO: Custom exception?
            return None
        if response.HasField("location"):
            return Location(response.location.latitude, response.location.longitude)
        else:
            return None

    async def set_quests_held(self, worker: str, quests_held: Optional[List[int]]) -> None:
        request: SetQuestsHeldRequest = SetQuestsHeldRequest()
        request.worker.name = worker
        if quests_held:
            request.quests_held.quest_ids.extend(quests_held)
        try:
            await self.SetQuestsHeld(request)
        except AioRpcError as e:
            logger.warning("Failed requesting setting quests held of {}: {}", worker, e)

    @cached(ttl=1)
    async def get_quests_held(self, worker: str) -> Optional[List[int]]:
        request: Worker = Worker()
        request.name = worker
        try:
            response: GetQuestsHeldResponse = await self.GetQuestsHeld(request)
        except AioRpcError as e:
            logger.warning("Failed requesting quests held of {}: {}", worker, e)
            # TODO: Custom exception?
            return None
        if not response.HasField("quests_held"):
            return None
        else:
            return [quest_id for quest_id in response.quests_held.quest_ids]
