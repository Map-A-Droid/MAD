import asyncio
from typing import Dict, Optional

import grpc
from google.protobuf import json_format
from grpc._cython.cygrpc import CompressionAlgorithm, CompressionLevel

from mapadroid.data_handler.mitm_data.holder.latest_mitm_data.LatestMitmDataEntry import \
    LatestMitmDataEntry
from mapadroid.data_handler.MitmMapper import MitmMapper
from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.grpc.compiled.mitm_mapper import mitm_mapper_pb2
from mapadroid.grpc.compiled.mitm_mapper.mitm_mapper_pb2 import (
    InjectedRequest, InjectionStatus,
    LastKnownLocationResponse, LastMoved, LatestMitmDataEntryRequest,
    LatestMitmDataEntryResponse, LatestMitmDataEntryUpdateRequest,
    LatestMitmDataFullResponse, LevelResponse, PokestopVisitsResponse, Stats,
    Worker, SetLevelRequest, SetPokestopVisitsRequest)
from mapadroid.grpc.compiled.shared.Ack_pb2 import Ack
from mapadroid.grpc.stubs.mitm_mapper.mitm_mapper_pb2_grpc import (
    MitmMapperServicer, add_MitmMapperServicer_to_server)
from mapadroid.utils.collections import Location
from mapadroid.utils.DatetimeWrapper import DatetimeWrapper
from mapadroid.utils.logging import LoggerEnums, get_logger
from mapadroid.utils.madGlobals import (MonSeenTypes, PositionType,
                                        TransportType, application_args)
from mapadroid.worker.WorkerType import WorkerType

logger = get_logger(LoggerEnums.mitm_mapper)


class MitmMapperServer(MitmMapperServicer, MitmMapper):
    def __init__(self, db_wrapper: DbWrapper):
        MitmMapper.__init__(self, db_wrapper=db_wrapper)
        self.__server = None

    async def start(self):
        await MitmMapper.start(self)
        max_message_length = 100 * 1024 * 1024
        options = [('grpc.max_message_length', max_message_length),
                   ('grpc.max_receive_message_length', max_message_length)]
        if application_args.mitmmapper_compression:
            options.extend([('grpc.default_compression_algorithm', CompressionAlgorithm.gzip),
                            ('grpc.grpc.default_compression_level', CompressionLevel.medium)])
        self.__server = grpc.aio.server(options=options)
        add_MitmMapperServicer_to_server(self, self.__server)
        address = f'{application_args.mitmmapper_ip}:{application_args.mitmmapper_port}'

        if application_args.mitmmapper_tls_cert_file and application_args.mitmmapper_tls_private_key_file:
            await self.__secure_port(address)
        else:
            await self.__insecure_port(address)
            logger.warning("Insecure MitmMapper gRPC API server")

        logger.info("Starting server on %s", address)
        await self.__server.start()

    async def __secure_port(self, address):
        with open(application_args.mitmmapper_tls_private_key_file, 'r') as keyfile, open(application_args.mitmmapper_tls_cert_file, 'r') as certfile:
            private_key = keyfile.read()
            certificate_chain = certfile.read()
        credentials = grpc.ssl_server_credentials(
            [(private_key, certificate_chain)]
        )
        self.__server.add_secure_port(address, credentials)

    async def __insecure_port(self, address):
        self.__server.add_insecure_port(address)

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
                worker_type=WorkerType(request.location_data.walker),
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
        # TODO: Threaded
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
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, self.__transform_single_response, latest)
        return result

    def __transform_single_response(self, latest):
        response: LatestMitmDataEntryResponse = LatestMitmDataEntryResponse()
        if not latest:
            return response
        self.__transform_latest_mitm_data_entry(response.entry, latest)
        return response

    def __transform_latest_mitm_data_entry(self, entry_message: mitm_mapper_pb2.LatestMitmDataEntry,
                                           latest) -> mitm_mapper_pb2.LatestMitmDataEntry:
        if latest.location:
            entry_message.location.latitude = latest.location.lat
            entry_message.location.longitude = latest.location.lng
        if latest.timestamp_of_data_retrieval:
            entry_message.timestamp_of_data_retrieval = latest.timestamp_of_data_retrieval
        if latest.timestamp_received:
            entry_message.timestamp_received = latest.timestamp_received
        if isinstance(latest.data, list):
            entry_message.some_list.extend(latest.data)
        else:
            entry_message.some_dictionary.update(latest.data)
        return entry_message

    async def RequestFullLatest(self, request: Worker,
                                context: grpc.aio.ServicerContext) -> LatestMitmDataFullResponse:
        data: Dict[str, LatestMitmDataEntry] = await self.get_full_latest_data(worker=request.name)
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, self.__generate_full_response, data.copy())
        return result

    def __generate_full_response(self, data: Dict[str, LatestMitmDataEntry]) -> LatestMitmDataFullResponse:
        response: LatestMitmDataFullResponse = LatestMitmDataFullResponse()
        for key, entry in data.items():
            try:
                self.__transform_latest_mitm_data_entry(response.latest[key], entry)
            except Exception as e:
                logger.exception(e)
        return response

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

    async def SetLevel(self, request: SetLevelRequest, context: grpc.aio.ServicerContext) -> Ack:
        await self.set_level(worker=request.worker.name,
                             level=request.level)
        response: Ack = Ack()
        return response

    async def SetPokestopVisits(self, request: SetPokestopVisitsRequest, context: grpc.aio.ServicerContext) -> Ack:
        await self.set_pokestop_visits(worker=request.worker.name,
                                       pokestop_visits=request.pokestop_visits)
        response: Ack = Ack()
        return response
