from typing import Dict, Optional, Set

from mapadroid.db.helper.SettingsDeviceHelper import SettingsDeviceHelper
from mapadroid.db.helper.SettingsPogoauthHelper import (LoginType,
                                                        SettingsPogoauthHelper)
from mapadroid.db.model import Base, SettingsDevice, SettingsPogoauth
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
            # The settings_device table contains a column simply referring to settings_pogoauth by string without a FK
            # Column: settings_device.ggl_login_mail
            # This relation needs to be updated accordingly by releasing the value from a device if the assigned device
            # changes or a device needs to have it assigned.
            existing_device_assignment: Optional[SettingsDevice] = await SettingsDeviceHelper.get_by_google_login(
                self._session, db_entry.username)
            if existing_device_assignment is not None and existing_device_assignment.device_id != value:
                # The device ID of the entry has been updated.
                existing_device_assignment.ggl_login_mail = None
            if value:
                # device_id is set in db_entry, simply write the ggl login username anyway
                device_to_assign_to: Optional[SettingsDevice] = await SettingsDeviceHelper.get(
                    self._session, self._get_instance_id(), value)
                device_to_assign_to.ggl_login_mail = db_entry.username
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
