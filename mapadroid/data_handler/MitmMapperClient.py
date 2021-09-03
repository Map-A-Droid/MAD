from datetime import datetime
from typing import List, Optional, Dict, Union

from mapadroid.data_handler.AbstractMitmMapper import AbstractMitmMapper
from mapadroid.data_handler.mitm_data.holder.latest_mitm_data.LatestMitmDataEntry import LatestMitmDataEntry
from mapadroid.grpc.compiled.mitm_mapper import mitm_mapper_pb2
from mapadroid.grpc.compiled.mitm_mapper.mitm_mapper_pb2 import Stats, LastMoved, LatestMitmDataEntryResponse, \
    LatestMitmDataEntryRequest, LatestMitmDataFullResponse, Worker, InventoryDataRequest, PokestopVisitsResponse, \
    LevelResponse, InjectionStatus, InjectedRequest, LastKnownLocationResponse
from mapadroid.grpc.stubs.mitm_mapper.mitm_mapper_pb2_grpc import MitmMapperStub
from mapadroid.utils.collections import Location
from mapadroid.utils.madGlobals import MonSeenTypes, PositionType, TransportType
from google.protobuf import json_format

from mapadroid.worker.WorkerType import WorkerType


class MitmMapperClient(MitmMapperStub, AbstractMitmMapper):
    async def stats_collect_wild_mon(self, worker: str, encounter_ids: List[int], time_scanned: datetime) -> None:
        request: Stats = Stats()
        request.worker.name = worker
        request.timestamp = int(time_scanned.timestamp())
        request.wild_mons.encounter_ids.extend(encounter_ids)
        await self.StatsCollect(request)

    async def stats_collect_mon_iv(self, worker: str, encounter_id: int, time_scanned: datetime,
                                   is_shiny: bool) -> None:
        request: Stats = Stats()
        request.worker.name = worker
        request.timestamp = int(time_scanned.timestamp())
        request.mon_iv.encounter_id = encounter_id
        request.mon_iv.is_shiny = is_shiny
        await self.StatsCollect(request)

    async def stats_collect_quest(self, worker: str, time_scanned: datetime) -> None:
        request: Stats = Stats()
        request.worker.name = worker
        request.timestamp = int(time_scanned.timestamp())
        await self.StatsCollect(request)

    async def stats_collect_raid(self, worker: str, time_scanned: datetime) -> None:
        request: Stats = Stats()
        request.worker.name = worker
        request.timestamp = int(time_scanned.timestamp())
        await self.StatsCollect(request)

    async def stats_collect_location_data(self, worker: str, location: Location, success: bool, fix_timestamp: int,
                                          position_type: PositionType, data_timestamp: int, walker: WorkerType,
                                          transport_type: TransportType, timestamp_of_record: int) -> None:
        request: Stats = Stats()
        request.worker.name = worker
        request.timestamp = timestamp_of_record
        request.location_data.location.latitude = location.lat
        request.location_data.location.longitude = location.lng
        request.location_data.success = success
        request.location_data.fix_timestamp = fix_timestamp
        request.location_data.data_timestamp = data_timestamp
        request.location_data.walker = walker.value
        # TODO: Probably gotta set it some other way...
        request.location_data.position_type = position_type.value
        request.location_data.transport_type = transport_type.value

        await self.StatsCollect(request)

    async def stats_collect_seen_type(self, encounter_ids: List[int], type_of_detection: MonSeenTypes,
                                      time_of_scan: datetime) -> None:
        request: Stats = Stats()
        request.timestamp = int(time_of_scan.timestamp())
        request.seen_type.encounter_ids.extend(encounter_ids)
        # TODO: Probably gotta set it some other way...
        request.seen_type.type_of_detection = type_of_detection.value
        await self.StatsCollect(request)

    async def get_last_possibly_moved(self, worker: str) -> int:
        response: LastMoved = await self.GetLastPossiblyMoved(name=worker)
        return response.timestamp

    async def update_latest(self, worker: str, key: str, value: Union[list, dict], timestamp_received_raw: float = None,
                            timestamp_received_receiver: float = None, location: Location = None) -> None:
        request: mitm_mapper_pb2.LatestMitmDataEntryUpdateRequest = mitm_mapper_pb2.LatestMitmDataEntryUpdateRequest()
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

    async def request_latest(self, worker: str, key: str) -> Optional[LatestMitmDataEntry]:
        request = LatestMitmDataEntryRequest()
        request.worker.name = worker
        request.key = str(key)
        response: LatestMitmDataEntryResponse = await self.RequestLatest(request)
        return self.__transform_proto_data_entry(response.entry) if response.entry else None

    def __transform_proto_data_entry(self, entry: mitm_mapper_pb2.LatestMitmDataEntry) -> LatestMitmDataEntry:
        location: Optional[Location] = None
        if entry.location:
            location: Location = Location(entry.location.latitude, entry.location.longitude)

        if entry.HasField(
                "some_dictionary"):
            data = entry.some_dictionary
        else:
            data = entry.some_list
        data = json_format.MessageToDict(data)
        entry: LatestMitmDataEntry = LatestMitmDataEntry(location=location,
                                                         timestamp_received=entry.timestamp_received,
                                                         timestamp_of_data_retrieval=entry.timestamp_of_data_retrieval,
                                                         data=data)
        return entry

    async def get_full_latest_data(self, worker: str) -> Dict[str, LatestMitmDataEntry]:
        request = Worker()
        request.name = worker
        response: LatestMitmDataFullResponse = await self.RequestFullLatest(request)
        # Iterate over map keys
        full_latest: Dict[str, LatestMitmDataEntry] = {}
        for key in response.latest:
            full_latest[key] = self.__transform_proto_data_entry(response.latest[key])
        return full_latest

    async def handle_inventory_data(self, worker: str, inventory_proto: dict) -> None:
        request: InventoryDataRequest = InventoryDataRequest()
        request.worker.name = worker
        request.inventory_data.update(inventory_proto)
        await self.HandleInventoryData(request)

    async def get_poke_stop_visits(self, worker: str) -> int:
        request: Worker = Worker()
        request.name = worker
        response: PokestopVisitsResponse = await self.GetPokestopVisits(request)
        return response.stops_visited

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
