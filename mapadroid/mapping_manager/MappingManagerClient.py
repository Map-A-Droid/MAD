from typing import Dict, List, Optional, Set

from aiocache import cached

from mapadroid.db.model import SettingsAuth
from mapadroid.grpc.compiled.mapping_manager.mapping_manager_pb2 import (
    AuthCredentialEntry, GetAllLoadedOriginsRequest,
    GetAllLoadedOriginsResponse, GetAllowedAuthenticationCredentialsRequest,
    GetAllowedAuthenticationCredentialsResponse,
    GetQuestLayerToScanOfOriginRequest, GetQuestLayerToScanOfOriginResponse,
    GetSafeItemsNotToDeleteRequest, GetSafeItemsNotToDeleteResponse,
    IsRoutemanagerOfOriginLevelmodeRequest,
    IsRoutemanagerOfOriginLevelmodeResponse)
from mapadroid.grpc.stubs.mapping_manager.mapping_manager_pb2_grpc import \
    MappingManagerStub
from mapadroid.mapping_manager.AbstractMappingManager import \
    AbstractMappingManager


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
    async def get_auths(self) -> Dict[str, SettingsAuth]:
        request = GetAllowedAuthenticationCredentialsRequest()
        response: GetAllowedAuthenticationCredentialsResponse = await self.GetAllowedAuthenticationCredentials(request)

        auths: Dict[str, SettingsAuth] = {}
        for username in response.allowed_credentials:
            auth_credential_entry: AuthCredentialEntry = response.allowed_credentials[username]
            local_auth_entry: SettingsAuth = SettingsAuth()
            local_auth_entry.username = auth_credential_entry.username
            local_auth_entry.password = auth_credential_entry.password
            local_auth_entry.auth_level = auth_credential_entry.auth_level
            auths[username] = local_auth_entry
        return auths

    @cached(ttl=10)
    async def routemanager_of_origin_is_levelmode(self, origin: str) -> bool:
        request = IsRoutemanagerOfOriginLevelmodeRequest()
        request.worker.name = origin
        response: IsRoutemanagerOfOriginLevelmodeResponse = await self.IsRoutemanagerOfOriginLevelmode(request)
        return response.is_levelmode

    async def routemanager_get_quest_layer_to_scan_of_origin(self, origin: str) -> Optional[int]:
        request = GetQuestLayerToScanOfOriginRequest()
        request.worker.name = origin
        response: GetQuestLayerToScanOfOriginResponse = await self.GetQuestLayerToScanOfOrigin(request)
        if response.HasField("layer"):
            return response.layer
        else:
            return None
