from typing import Dict, Optional, Set

from mapadroid.db.helper.SettingsAuthHelper import SettingsAuthHelper
from mapadroid.db.model import Base, SettingsAuth
from mapadroid.db.resource_definitions.Auth import Auth
from mapadroid.madmin.endpoints.api.resources.AbstractResourceEndpoint import \
    AbstractResourceEndpoint


class AuthEndpoint(AbstractResourceEndpoint):
    def _attributes_to_ignore(self) -> Set[str]:
        return {"auth_id", "guid"}

    async def _fetch_all_from_db(self, **kwargs) -> Dict[int, Base]:
        return await SettingsAuthHelper.get_all_mapped(self._session, self._get_instance_id())

    def _resource_info(self, obj: Optional[Base] = None) -> Dict:
        return Auth.configuration

    async def _fetch_from_db(self, identifier, **kwargs) -> Optional[Base]:
        auth: Optional[SettingsAuth] = await SettingsAuthHelper.get(self._session, self._get_instance_id(),
                                                                    identifier)
        return auth

    async def _create_instance(self, identifier):
        auth = SettingsAuth()
        auth.instance_id = self._get_instance_id()
        auth.auth_id = identifier
        return auth
