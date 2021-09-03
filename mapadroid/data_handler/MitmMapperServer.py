from typing import Optional, Dict

import grpc

from mapadroid.data_handler.MitmMapper import MitmMapper
from mapadroid.data_handler.mitm_data.holder.latest_mitm_data.LatestMitmDataEntry import LatestMitmDataEntry
from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.grpc.compiled.mitm_mapper import mitm_mapper_pb2
from mapadroid.grpc.compiled.mitm_mapper.mitm_mapper_pb2 import Stats, Worker, LastMoved, \
    LatestMitmDataEntryUpdateRequest, LatestMitmDataEntryRequest, LatestMitmDataEntryResponse, \
    LatestMitmDataFullResponse, InventoryDataRequest, PokestopVisitsResponse, LevelResponse, InjectionStatus, \
    InjectedRequest, LastKnownLocationResponse
from mapadroid.grpc.compiled.shared.Ack_pb2 import Ack

from mapadroid.grpc.stubs.mitm_mapper.mitm_mapper_pb2_grpc import MitmMapperServicer, add_MitmMapperServicer_to_server
from mapadroid.utils.DatetimeWrapper import DatetimeWrapper
from mapadroid.utils.collections import Location
from mapadroid.utils.logging import get_logger, LoggerEnums
from mapadroid.utils.madGlobals import PositionType, TransportType, MonSeenTypes
from google.protobuf import json_format

logger = get_logger(LoggerEnums.mitm_mapper)


class MitmMapperServer(MitmMapperServicer, MitmMapper):
    def __init__(self, db_wrapper: DbWrapper):
        MitmMapper.__init__(self, db_wrapper=db_wrapper)
        self.__server = None

    async def start(self):
        await MitmMapper.start(self)
        options = [('grpc.max_message_length', 100 * 1024 * 1024)]
        self.__server = grpc.aio.server(options=options)
        add_MitmMapperServicer_to_server(self, self.__server)
        listen_addr = '[::]:50051'
        self.__server.add_insecure_port(listen_addr)
        logger.info("Starting server on %s", listen_addr)
        await self.__server.start()

    async def shutdown(self):
        await MitmMapper.shutdown(self)
        if self.__server:
            await self.__server.stop(0)

    async def StatsCollect(self, request: Stats, context: grpc.aio.ServicerContext) -> Ack:
        # depending on the data_to_collect we need to parse fields..
        if request.HasField("wild_mons"):
            await self.stats_collect_wild_mon(
                request.worker.name, encounter_ids=request.wild_mons.encounter_ids,
                time_scanned=DatetimeWrapper.fromtimestamp(request.timestamp))
        elif request.HasField("mon_iv"):
            await self.stats_collect_mon_iv(
                request.worker.name, encounter_id=request.mon_iv.encounter_id,
                is_shiny=request.mon_iv.is_shiny,
                time_scanned=DatetimeWrapper.fromtimestamp(request.timestamp))
        elif request.HasField("quest"):
            await self.stats_collect_quest(
                request.worker.name,
                time_scanned=DatetimeWrapper.fromtimestamp(request.timestamp))
        elif request.HasField("raid"):
            await self.stats_collect_raid(
                request.worker.name,
                time_scanned=DatetimeWrapper.fromtimestamp(request.timestamp))
        elif request.HasField("location_data"):
            if not request.location_data.HasField("location"):
                # TODO: Ack failure indicator?
                return Ack()
            location = Location(request.location_data.location.latitude,
                                request.location_data.location.longitude)
            await self.stats_collect_location_data(
                request.worker.name,
                location=location,
                success=request.location_data.success,
                fix_timestamp=request.location_data.fix_timestamp,
                data_timestamp=request.location_data.data_timestamp,
                # TODO: Probably gotta read value of protobuf enum...
                position_type=PositionType(request.location_data.position_type),
                walker=request.location_data.walker,
                transport_type=TransportType(request.location_data.transport_type),
                timestamp_of_record=request.timestamp)
        elif request.HasField("seen_type"):
            await self.stats_collect_seen_type(
                encounter_ids=request.seen_type.encounter_ids,
                type_of_detection=MonSeenTypes(request.seen_type.type_of_detection),
                time_of_scan=DatetimeWrapper.fromtimestamp(request.timestamp))
        return Ack()

    async def GetLastPossiblyMoved(self, request: Worker, context: grpc.aio.ServicerContext) -> LastMoved:
        response: LastMoved = LastMoved()
        response.timestamp = await self.get_last_possibly_moved(request.name)
        return response

    async def UpdateLatest(self, request: LatestMitmDataEntryUpdateRequest,
                           context: grpc.aio.ServicerContext) -> Ack:
        value = None
        if request.data.HasField("some_dictionary"):
            value = request.data.some_dictionary
        else:
            value = request.data.some_list
        value = json_format.MessageToDict(value)
        await self.update_latest(
            worker=request.worker.name, key=request.key,
            timestamp_received_raw=request.data.timestamp_received,
            timestamp_received_receiver=request.data.timestamp_of_data_retrieval,
            location=Location(request.data.location.latitude,
                              request.data.location.longitude),
            value=value
        )
        return Ack()

    async def RequestLatest(self, request: LatestMitmDataEntryRequest,
                            context: grpc.aio.ServicerContext) -> LatestMitmDataEntryResponse:
        latest: Optional[LatestMitmDataEntry] = await self.request_latest(
            request.worker.name, request.key)
        response: LatestMitmDataEntryResponse = LatestMitmDataEntryResponse()
        if not latest:
            return response
        response.entry.CopyFrom(self.__transform_latest_mitm_data_entry(latest))
        return response

    def __transform_latest_mitm_data_entry(self, latest) -> mitm_mapper_pb2.LatestMitmDataEntry:
        entry: mitm_mapper_pb2.LatestMitmDataEntry = mitm_mapper_pb2.LatestMitmDataEntry()
        if latest.location:
            entry.location.latitude = latest.location.lat
            entry.location.longitude = latest.location.lng
        if latest.timestamp_of_data_retrieval:
            entry.timestamp_of_data_retrieval = latest.timestamp_of_data_retrieval
        if latest.timestamp_received:
            entry.timestamp_received = latest.timestamp_received
        if isinstance(latest.data, list):
            entry.some_list.extend(latest.data)
        else:
            entry.some_dictionary.update(latest.data)
        return entry

    async def RequestFullLatest(self, request: Worker,
                                context: grpc.aio.ServicerContext) -> LatestMitmDataFullResponse:
        response: LatestMitmDataFullResponse = LatestMitmDataFullResponse()
        data: Dict[str, LatestMitmDataEntry] = await self.get_full_latest_data(worker=request.name)
        for key, entry in data.items():
            try:
                proto_entry: mitm_mapper_pb2.LatestMitmDataEntry = self.__transform_latest_mitm_data_entry(entry)
                response.latest[key].CopyFrom(proto_entry)
            except Exception as e:
                logger.exception(e)
        return response

    async def HandleInventoryData(self, request: InventoryDataRequest,
                                  context: grpc.aio.ServicerContext) -> Ack:
        inventory_data = json_format.MessageToDict(request.inventory_data)
        await self.handle_inventory_data(worker=request.worker.name,
                                         inventory_proto=inventory_data)
        return Ack()

    async def GetPokestopVisits(self, request: Worker,
                                context: grpc.aio.ServicerContext) -> PokestopVisitsResponse:
        stops_visited: int = await self.get_poke_stop_visits(request.name)
        return PokestopVisitsResponse(stops_visited=stops_visited)

    async def GetLevel(self, request: Worker,
                       context: grpc.aio.ServicerContext) -> LevelResponse:
        level: int = await self.get_level(request.name)
        return LevelResponse(level=level)

    async def GetInjectionStatus(self, request: Worker,
                                 context: grpc.aio.ServicerContext) -> InjectionStatus:
        is_injected: bool = await self.get_injection_status(worker=request.name)
        return InjectionStatus(is_injected=is_injected)

    async def SetInjected(self, request: InjectedRequest,
                          context: grpc.aio.ServicerContext) -> Ack:
        await self.set_injection_status(worker=request.worker.name,
                                        status=request.injected.is_injected)
        return Ack()

    async def GetLastKnownLocation(self, request: Worker,
                                   context: grpc.aio.ServicerContext) -> LastKnownLocationResponse:
        location: Optional[Location] = await self.get_last_known_location(request.name)
        response: LastKnownLocationResponse = LastKnownLocationResponse()
        if not location:
            return response
        response.location.latitude = location.lat
        response.location.longitude = location.lng
        return response
