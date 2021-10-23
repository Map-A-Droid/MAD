from typing import Dict, Optional, Set, List

from mapadroid.db.helper.AutoconfigFileHelper import AutoconfigFileHelper
from mapadroid.db.helper.SettingsAuthHelper import SettingsAuthHelper
from mapadroid.db.model import Base, SettingsAuth, AutoconfigFile
from mapadroid.db.resource_definitions.Auth import Auth
from mapadroid.madmin.endpoints.api.resources.AbstractResourceEndpoint import \
    AbstractResourceEndpoint


class AuthEndpoint(AbstractResourceEndpoint):
    async def _get_unmet_dependencies(self, db_entry: SettingsAuth) -> Optional[Dict[int, str]]:
        assigned_to_auth: List[AutoconfigFile] = await AutoconfigFileHelper.get_assigned_to_auth(self._session, db_entry)
        if not assigned_to_auth:
            return None
        else:
            mapped: Dict[int, str] = {0: f"Used in autconfig file {autoconfig_file.name}" for autoconfig_file in assigned_to_auth}
            return mapped

    async def _delete_connected_prior(self, db_entry):
        pass

    async def _delete_connected_post(self, db_entry):
        pass

    def _attributes_to_ignore(self) -> Set[str]:
        return {"auth_id", "guid", "instance_id"}

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
