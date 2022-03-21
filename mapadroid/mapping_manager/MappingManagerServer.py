from typing import Optional, Dict, Set, List

import grpc
from grpc._cython.cygrpc import CompressionAlgorithm, CompressionLevel

from mapadroid.grpc.compiled.mapping_manager.mapping_manager_pb2 import GetAllowedAuthenticationCredentialsRequest, \
    GetAllowedAuthenticationCredentialsResponse, GetAllLoadedOriginsRequest, GetAllLoadedOriginsResponse, \
    GetSafeItemsNotToDeleteRequest, GetSafeItemsNotToDeleteResponse, IsRoutemanagerOfOriginLevelmodeRequest, \
    IsRoutemanagerOfOriginLevelmodeResponse, GetQuestLayerToScanOfOriginRequest, GetQuestLayerToScanOfOriginResponse
from mapadroid.grpc.stubs.mapping_manager.mapping_manager_pb2_grpc import MappingManagerServicer, \
    add_MappingManagerServicer_to_server
from mapadroid.mapping_manager.AbstractMappingManager import AbstractMappingManager
from mapadroid.utils.logging import get_logger, LoggerEnums
from mapadroid.utils.madGlobals import application_args

logger = get_logger(LoggerEnums.mapping_manager)


class MappingManagerServer(MappingManagerServicer):
    def __init__(self, mapping_manager_impl: AbstractMappingManager):
        self.__mapping_manager_impl: AbstractMappingManager = mapping_manager_impl
        self.__server = None

    async def start(self):
        max_message_length = 100 * 1024 * 1024
        options = [('grpc.max_message_length', max_message_length),
                   ('grpc.max_receive_message_length', max_message_length)]
        if application_args.mappingmanager_compression:
            options.extend([('grpc.default_compression_algorithm', CompressionAlgorithm.gzip),
                            ('grpc.grpc.default_compression_level', CompressionLevel.medium)])
        self.__server = grpc.aio.server(options=options)
        add_MappingManagerServicer_to_server(self, self.__server)
        address = f'{application_args.mappingmanager_ip}:{application_args.mappingmanager_port}'
        if application_args.mappingmanager_tls_cert_file and application_args.mappingmanager_tls_private_key_file:
            await self.__secure_port(address)
        else:
            await self.__insecure_port(address)

        logger.info("Starting server listening on {}", address)
        await self.__server.start()

    async def __secure_port(self, address):
        with open(application_args.mappingmanager_tls_private_key_file, 'r') as keyfile, open(
                application_args.mappingmanager_tls_cert_file, 'r') as certfile:
            private_key = keyfile.read()
            certificate_chain = certfile.read()
        credentials = grpc.ssl_server_credentials(
            [(private_key, certificate_chain)]
        )
        self.__server.add_secure_port(address, credentials)

    async def __insecure_port(self, address):
        self.__server.add_insecure_port(address)
        logger.warning("Insecure MappingManager gRPC API server")

    async def shutdown(self):
        if self.__server:
            await self.__server.stop(0)

    async def GetAllowedAuthenticationCredentials(self, request: GetAllowedAuthenticationCredentialsRequest,
                                                  context: grpc.aio.ServicerContext) -> GetAllowedAuthenticationCredentialsResponse:
        response: GetAllowedAuthenticationCredentialsResponse = GetAllowedAuthenticationCredentialsResponse()
        auths_allowed: Optional[Dict[str, str]] = await self.__mapping_manager_impl.get_auths()
        if auths_allowed:
            for username, password in auths_allowed.items():
                response.allowed_credentials[username] = password
        return response

    async def GetAllLoadedOrigins(self, request: GetAllLoadedOriginsRequest,
                                  context: grpc.aio.ServicerContext) -> GetAllLoadedOriginsResponse:
        response = GetAllLoadedOriginsResponse()
        auths_allowed: Set[str] = await self.__mapping_manager_impl.get_all_loaded_origins()

        response.loaded_origins.extend(auths_allowed)
        return response

    async def GetSafeItemsNotToDelete(self, request: GetSafeItemsNotToDeleteRequest,
                                      context: grpc.aio.ServicerContext) -> GetSafeItemsNotToDeleteResponse:
        response = GetSafeItemsNotToDeleteResponse()
        safe_items: List[int] = await self.__mapping_manager_impl.get_safe_items(origin=request.worker.name)
        response.item_ids.extend(safe_items)
        return response

    async def IsRoutemanagerOfOriginLevelmode(self, request: IsRoutemanagerOfOriginLevelmodeRequest,
                                              context: grpc.aio.ServicerContext) -> IsRoutemanagerOfOriginLevelmodeResponse:
        response = IsRoutemanagerOfOriginLevelmodeResponse()
        response.is_levelmode = await self.__mapping_manager_impl.routemanager_of_origin_is_levelmode(
            origin=request.worker.name)
        return response

    async def GetQuestLayerToScanOfOrigin(self, request: GetQuestLayerToScanOfOriginRequest,
                                          context: grpc.aio.ServicerContext) -> GetQuestLayerToScanOfOriginResponse:
        response: GetQuestLayerToScanOfOriginResponse = GetQuestLayerToScanOfOriginResponse()
        quest_layer_to_scan: Optional[int] = await self.__mapping_manager_impl\
            .routemanager_get_quest_layer_to_scan_of_origin(request.worker.name)
        if quest_layer_to_scan is not None:
            response.layer = quest_layer_to_scan
        return response
