import asyncio
from typing import Optional, Dict, Union
from aiocache import cached

from mapadroid.data_handler.mitm_data.AbstractMitmMapper import AbstractMitmMapper
from mapadroid.data_handler.mitm_data.holder.latest_mitm_data.LatestMitmDataEntry import LatestMitmDataEntry
from mapadroid.grpc.compiled.mitm_mapper import mitm_mapper_pb2
from mapadroid.grpc.compiled.mitm_mapper.mitm_mapper_pb2 import LastMoved, LatestMitmDataEntryResponse, \
    LatestMitmDataEntryRequest, LatestMitmDataFullResponse, PokestopVisitsResponse, \
    LevelResponse, InjectionStatus, InjectedRequest, LastKnownLocationResponse, SetLevelRequest, \
    SetPokestopVisitsRequest
from mapadroid.grpc.compiled.shared.Worker_pb2 import Worker
from mapadroid.grpc.stubs.mitm_mapper.mitm_mapper_pb2_grpc import MitmMapperStub
from mapadroid.utils.collections import Location
from google.protobuf import json_format

from loguru import logger


class MitmMapperClient(MitmMapperStub, AbstractMitmMapper):
    def __init__(self, channel):
        super().__init__(channel)
        self._level_cache: Dict[str, int] = {}
        self._pokestop_visits_cache: Dict[str, int] = {}

    # Cache the update parameters to not spam it...
    @cached(ttl=300)
    async def set_level(self, worker: str, level: int) -> None:
        if self._level_cache.get(worker, 0) == level:
            return
        else:
            self._level_cache[worker] = level
        logger.debug("Submitting level {}", level)
        request: SetLevelRequest = SetLevelRequest()
        request.worker.name = worker
        request.level = level
        await self.SetLevel(request)

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
        await self.SetPokestopVisits(request)

    async def get_last_possibly_moved(self, worker: str) -> int:
        response: LastMoved = await self.GetLastPossiblyMoved(name=worker)
        return response.timestamp

    async def update_latest(self, worker: str, key: str, value: Union[list, dict], timestamp_received_raw: float = None,
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
        else:
            raise ValueError("Cannot handle data")
        await self.UpdateLatest(request)

    async def request_latest(self, worker: str, key: str,
                             timestamp_earliest: Optional[int] = None) -> Optional[LatestMitmDataEntry]:
        request = LatestMitmDataEntryRequest()
        request.worker.name = worker
        request.key = str(key)
        if timestamp_earliest:
            request.timestamp_earliest = timestamp_earliest
        response: LatestMitmDataEntryResponse = await self.RequestLatest(request)
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

    async def get_full_latest_data(self, worker: str) -> Dict[str, LatestMitmDataEntry]:
        request = Worker()
        request.name = worker
        response: LatestMitmDataFullResponse = await self.RequestFullLatest(request)
        loop = asyncio.get_running_loop()
        full_latest: Dict[str, LatestMitmDataEntry] = await loop.run_in_executor(
            None, self.__full_transformation, response)
        return full_latest

    def __full_transformation(self, response: LatestMitmDataFullResponse) -> Dict[str, LatestMitmDataEntry]:
        full_latest: Dict[str, LatestMitmDataEntry] = {}
        for key in response.latest:
            full_latest[key] = self.__transform_proto_data_entry(response.latest[key])
        return full_latest

    @cached(ttl=30)
    async def get_poke_stop_visits(self, worker: str) -> int:
        request: Worker = Worker()
        request.name = worker
        response: PokestopVisitsResponse = await self.GetPokestopVisits(request)
        return response.stops_visited

    @cached(ttl=60)
    async def get_level(self, worker: str) -> int:
        request: Worker = Worker()
        request.name = worker
        response: LevelResponse = await self.GetLevel(request)
        return response.level

    async def get_injection_status(self, worker: str) -> bool:
        request: Worker = Worker()
        request.name = worker
        response: InjectionStatus = await self.GetInjectionStatus(request)
        return response.is_injected

    async def set_injection_status(self, worker: str, status: bool) -> None:
        request: InjectedRequest = InjectedRequest()
        request.worker.name = worker
        request.injected.is_injected = status
        await self.SetInjected(request)

    async def get_last_known_location(self, worker: str) -> Optional[Location]:
        request: Worker = Worker()
        request.name = worker
        response: LastKnownLocationResponse = await self.GetLastKnownLocation(request)
        if response.HasField("location"):
            return Location(response.location.latitude, response.location.longitude)
        else:
            return None
