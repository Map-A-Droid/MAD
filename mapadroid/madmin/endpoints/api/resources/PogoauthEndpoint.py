from typing import Dict, Optional, Set

from mapadroid.db.helper.SettingsPogoauthHelper import (LoginType,
                                                        SettingsPogoauthHelper)
from mapadroid.db.model import Base, SettingsPogoauth
from mapadroid.db.resource_definitions.Pogoauth import Pogoauth
from mapadroid.madmin.endpoints.api.resources.AbstractResourceEndpoint import \
    AbstractResourceEndpoint


class PogoauthEndpoint(AbstractResourceEndpoint):
    async def _get_unmet_dependencies(self, db_entry: SettingsPogoauth) -> Optional[Dict[int, str]]:
        if db_entry.device_id is not None:
            return {
                db_entry.device_id: f"PogoAuth entry {db_entry.account_id} is still assigned to device {db_entry.device}"}
        else:
            return None

    async def _handle_additional_keys(self, db_entry: SettingsPogoauth, key: str, value) -> bool:
        if key == "device_id" and db_entry.login_type == LoginType.GOOGLE.value:
            # Device ID is a one-way assignment
            db_entry.device_id = value
            return True
        return False

    async def _delete_connected_prior(self, db_entry):
        pass

    async def _delete_connected_post(self, db_entry):
        pass

    def _attributes_to_ignore(self) -> Set[str]:
        return {"account_id", "guid"}

    async def _fetch_all_from_db(self, **kwargs) -> Dict[int, Base]:
        return await SettingsPogoauthHelper.get_all_mapped(self._session, self._get_instance_id())

    def _resource_info(self, obj: Optional[Base] = None) -> Dict:
        return Pogoauth.configuration

    async def _fetch_from_db(self, identifier, **kwargs) -> Optional[Base]:
        return await SettingsPogoauthHelper.get(self._session, self._get_instance_id(), identifier)

    async def _create_instance(self, identifier):
        auth: SettingsPogoauth = SettingsPogoauth()
        auth.instance_id = self._get_instance_id()
        auth.account_id = identifier
        return auth
