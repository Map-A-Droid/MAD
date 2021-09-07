from typing import Optional, Dict, Set, List

import grpc

from mapadroid.grpc.compiled.mapping_manager.mapping_manager_pb2 import GetAllowedAuthenticationCredentialsRequest, \
    GetAllowedAuthenticationCredentialsResponse, GetAllLoadedOriginsRequest, GetAllLoadedOriginsResponse, \
    GetSafeItemsNotToDeleteRequest, GetSafeItemsNotToDeleteResponse, IsRoutemanagerOfOriginLevelmodeRequest, \
    IsRoutemanagerOfOriginLevelmodeResponse
from mapadroid.grpc.stubs.mapping_manager.mapping_manager_pb2_grpc import MappingManagerServicer
from mapadroid.mapping_manager.AbstractMappingManager import AbstractMappingManager


class MappingManagerServer(MappingManagerServicer):
    def __init__(self, mapping_manager_impl: AbstractMappingManager):
        self.__mapping_manager_impl: AbstractMappingManager = mapping_manager_impl

    async def GetAllowedAuthenticationCredentials(self, request: GetAllowedAuthenticationCredentialsRequest,
                                                  context: grpc.aio.ServicerContext) -> GetAllowedAuthenticationCredentialsResponse:
        response: GetAllowedAuthenticationCredentialsResponse = GetAllowedAuthenticationCredentialsResponse()
        auths_allowed: Optional[Dict[str, str]] = await self.__mapping_manager_impl.get_auths()
        response.allowed_credentials.CopyFrom(auths_allowed)
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
