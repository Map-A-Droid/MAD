from typing import Optional, Dict, List, Set

from aiocache import cached

from mapadroid.grpc.compiled.mapping_manager.mapping_manager_pb2 import GetAllLoadedOriginsResponse, \
    GetAllLoadedOriginsRequest, GetSafeItemsNotToDeleteRequest, GetSafeItemsNotToDeleteResponse, \
    GetAllowedAuthenticationCredentialsRequest, GetAllowedAuthenticationCredentialsResponse, \
    IsRoutemanagerOfOriginLevelmodeRequest, IsRoutemanagerOfOriginLevelmodeResponse, \
    GetQuestLayerToScanOfOriginResponse, GetQuestLayerToScanOfOriginRequest
from mapadroid.grpc.stubs.mapping_manager.mapping_manager_pb2_grpc import MappingManagerStub
from mapadroid.mapping_manager.AbstractMappingManager import AbstractMappingManager


class MappingManagerClient(MappingManagerStub, AbstractMappingManager):
    @cached(ttl=360)
    async def get_all_loaded_origins(self) -> Set[str]:
        request: GetAllLoadedOriginsRequest = GetAllLoadedOriginsRequest()
        response: GetAllLoadedOriginsResponse = await self.GetAllLoadedOrigins(request)
        loaded_origins: Set[str] = set()
        loaded_origins.update(response.loaded_origins)
        return loaded_origins

    @cached(ttl=360)
    async def get_safe_items(self, origin: str) -> List[int]:
        request = GetSafeItemsNotToDeleteRequest()
        request.worker.name = origin
        response: GetSafeItemsNotToDeleteResponse = await self.GetSafeItemsNotToDelete(request)
        item_ids: List[int] = []
        item_ids.extend(response.item_ids)
        return item_ids

    @cached(ttl=360)
    async def get_auths(self) -> Optional[Dict[str, str]]:
        request = GetAllowedAuthenticationCredentialsRequest()
        response: GetAllowedAuthenticationCredentialsResponse = await self.GetAllowedAuthenticationCredentials(request)

        auths: Dict[str, str] = {}
        for username in response.allowed_credentials:
            auths[username] = response.allowed_credentials[username]
        return auths if auths else None

    @cached(ttl=60)
    async def routemanager_of_origin_is_levelmode(self, origin: str) -> bool:
        request = IsRoutemanagerOfOriginLevelmodeRequest()
        request.worker.name = origin
        response: IsRoutemanagerOfOriginLevelmodeResponse = await self.IsRoutemanagerOfOriginLevelmode(request)
        return response.is_levelmode

    async def routemanager_get_quest_layer_to_scan_of_origin(self, origin: str) -> Optional[int]:
        request = GetQuestLayerToScanOfOriginRequest()
        request.worker.name = origin
        response: GetQuestLayerToScanOfOriginResponse = await self.GetQuestLayerToScanOfOrigin(request)
        return response.layer
