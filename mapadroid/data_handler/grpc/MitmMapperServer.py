import asyncio
from typing import Dict, Optional

import grpc
from google.protobuf import json_format
from grpc._cython.cygrpc import CompressionAlgorithm, CompressionLevel

from mapadroid.data_handler.mitm_data.holder.latest_mitm_data.LatestMitmDataEntry import \
    LatestMitmDataEntry
from mapadroid.data_handler.mitm_data.MitmMapper import MitmMapper
from mapadroid.grpc.compiled.mitm_mapper import mitm_mapper_pb2
from mapadroid.grpc.compiled.mitm_mapper.mitm_mapper_pb2 import (
    InjectedRequest, InjectionStatus,
    LastKnownLocationResponse, LastMoved, LatestMitmDataEntryRequest,
    LatestMitmDataEntryResponse, LatestMitmDataEntryUpdateRequest,
    LatestMitmDataFullResponse, LevelResponse, PokestopVisitsResponse,
    SetLevelRequest, SetPokestopVisitsRequest)
from mapadroid.grpc.compiled.shared.Ack_pb2 import Ack
from mapadroid.grpc.compiled.shared.Worker_pb2 import Worker
from mapadroid.grpc.stubs.mitm_mapper.mitm_mapper_pb2_grpc import (
    MitmMapperServicer, add_MitmMapperServicer_to_server)
from mapadroid.utils.collections import Location
from mapadroid.utils.logging import LoggerEnums, get_logger
from mapadroid.utils.madGlobals import (application_args)

logger = get_logger(LoggerEnums.mitm_mapper)


class MitmMapperServer(MitmMapperServicer, MitmMapper):
    def __init__(self):
        MitmMapper.__init__(self)
        self.__server = None

    async def start(self):
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

        logger.info("Starting to listen on {}", address)
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
        if self.__server:
            await self.__server.stop(0)

    async def GetLastPossiblyMoved(self, request: Worker, context: grpc.aio.ServicerContext) -> LastMoved:
        logger.debug("GetLastPossiblyMoved called")
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
        logger.debug("UpdateLatest called")
        loop = asyncio.get_running_loop()
        json_formatted = await loop.run_in_executor(None, json_format.MessageToDict, value)
        await self.update_latest(
            worker=request.worker.name, key=request.key,
            timestamp_received_raw=request.data.timestamp_received,
            timestamp_received_receiver=request.data.timestamp_of_data_retrieval,
            location=Location(request.data.location.latitude,
                              request.data.location.longitude),
            value=json_formatted
        )
        return Ack()

    async def RequestLatest(self, request: LatestMitmDataEntryRequest,
                            context: grpc.aio.ServicerContext) -> LatestMitmDataEntryResponse:
        logger.debug("RequestLatest called")
        timestamp_earliest: Optional[int] = None
        if request.HasField("timestamp_earliest"):
            timestamp_earliest = request.timestamp_earliest
        logger.debug("Checking for proto after {}", timestamp_earliest)
        latest: Optional[LatestMitmDataEntry] = await self.request_latest(
            request.worker.name, request.key, timestamp_earliest)
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
        elif isinstance(latest.data, dict):
            logger.debug("Placing dict data")
            entry_message.some_dictionary.update(latest.data)
        return entry_message

    async def RequestFullLatest(self, request: Worker,
                                context: grpc.aio.ServicerContext) -> LatestMitmDataFullResponse:
        logger.debug("RequestFullLatest called")
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
        logger.debug("GetPokestopVisits called")
        stops_visited: int = await self.get_poke_stop_visits(request.name)
        return PokestopVisitsResponse(stops_visited=stops_visited)

    async def GetLevel(self, request: Worker,
                       context: grpc.aio.ServicerContext) -> LevelResponse:
        logger.debug("GetLevel called")
        level: int = await self.get_level(request.name)
        return LevelResponse(level=level)

    async def GetInjectionStatus(self, request: Worker,
                                 context: grpc.aio.ServicerContext) -> InjectionStatus:
        logger.debug("GetInjectionStatus called")
        is_injected: bool = await self.get_injection_status(worker=request.name)
        return InjectionStatus(is_injected=is_injected)

    async def SetInjected(self, request: InjectedRequest,
                          context: grpc.aio.ServicerContext) -> Ack:
        logger.debug("SetInjected called")
        await self.set_injection_status(worker=request.worker.name,
                                        status=request.injected.is_injected)
        return Ack()

    async def GetLastKnownLocation(self, request: Worker,
                                   context: grpc.aio.ServicerContext) -> LastKnownLocationResponse:
        logger.debug("GetLastKnownLocation called")
        location: Optional[Location] = await self.get_last_known_location(request.name)
        response: LastKnownLocationResponse = LastKnownLocationResponse()
        if not location:
            return response
        response.location.latitude = location.lat
        response.location.longitude = location.lng
        return response

    async def SetLevel(self, request: SetLevelRequest, context: grpc.aio.ServicerContext) -> Ack:
        logger.debug("SetLevel called")
        await self.set_level(worker=request.worker.name,
                             level=request.level)
        response: Ack = Ack()
        return response

    async def SetPokestopVisits(self, request: SetPokestopVisitsRequest, context: grpc.aio.ServicerContext) -> Ack:
        logger.debug("SetPokestopVisits called")
        await self.set_pokestop_visits(worker=request.worker.name,
                                       pokestop_visits=request.pokestop_visits)
        response: Ack = Ack()
        return response
