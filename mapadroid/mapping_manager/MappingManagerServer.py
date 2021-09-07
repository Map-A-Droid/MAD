from typing import Optional, Dict, Set, List

import grpc

from mapadroid.grpc.compiled.mapping_manager.mapping_manager_pb2 import GetAllowedAuthenticationCredentialsRequest, \
    GetAllowedAuthenticationCredentialsResponse, GetAllLoadedOriginsRequest, GetAllLoadedOriginsResponse, \
    GetSafeItemsNotToDeleteRequest, GetSafeItemsNotToDeleteResponse, IsRoutemanagerOfOriginLevelmodeRequest, \
    IsRoutemanagerOfOriginLevelmodeResponse
from mapadroid.grpc.stubs.mapping_manager.mapping_manager_pb2_grpc import MappingManagerServicer, \
    add_MappingManagerServicer_to_server
from mapadroid.mapping_manager.AbstractMappingManager import AbstractMappingManager
from mapadroid.utils.logging import get_logger, LoggerEnums

logger = get_logger(LoggerEnums.mapping_manager)


class MappingManagerServer(MappingManagerServicer):
    def __init__(self, mapping_manager_impl: AbstractMappingManager):
        self.__mapping_manager_impl: AbstractMappingManager = mapping_manager_impl
        self.__server = None

    async def start(self):
        max_message_length = 100 * 1024 * 1024
        options = [('grpc.max_message_length', max_message_length),
                   ('grpc.max_receive_message_length', max_message_length)]
        self.__server = grpc.aio.server(options=options)
        add_MappingManagerServicer_to_server(self, self.__server)
        listen_addr = '[::]:50052'
        self.__server.add_insecure_port(listen_addr)
        logger.info("Starting server on %s", listen_addr)
        await self.__server.start()

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
        response.is_levelmode = await self.__mapping_manager_impl.routemanager_of_origin_is_levelmode(origin=request.worker.name)
        return response
