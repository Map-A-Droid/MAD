from typing import Dict, List, Optional, Set

from aiohttp import web

from mapadroid.db.helper.SettingsDeviceHelper import SettingsDeviceHelper
from mapadroid.db.helper.SettingsPogoauthHelper import (LoginType,
                                                        SettingsPogoauthHelper)
from mapadroid.db.helper.TrsVisitedHelper import TrsVisitedHelper
from mapadroid.db.model import Base, SettingsDevice, SettingsPogoauth
from mapadroid.db.resource_definitions.Device import Device
from mapadroid.madmin.endpoints.api.resources.AbstractResourceEndpoint import \
    AbstractResourceEndpoint


class DeviceEndpoint(AbstractResourceEndpoint):
    async def _delete_connected_post(self, db_entry):
        pass

    async def _delete_connected_prior(self, db_entry):
        assigned_to_device: List[SettingsPogoauth] = await SettingsPogoauthHelper \
            .get_assigned_to_device(self._session, self._get_instance_id(), db_entry.device_id)
        for assigned in assigned_to_device:
            assigned.device_id = None

    async def _handle_additional_keys(self, db_entry: SettingsDevice, key: str, value) -> bool:
        # ptc_login is an array of IDs that are to be used. We need to set the IDs accordingly
        if key == "ptc_login":
            pogoauth_ids_to_use: Set[int] = set([int(x) for x in value])
            assigned_to_device: List[SettingsPogoauth] = await SettingsPogoauthHelper \
                .get_assigned_to_device(self._session, self._get_instance_id(), db_entry.device_id)
            all_pogoauth_mapped: Dict[int, SettingsPogoauth] = await SettingsPogoauthHelper \
                .get_all_mapped(self._session, self._get_instance_id())

            # First remove any that are not in the set to use
            for assigned in assigned_to_device:
                if assigned.account_id not in pogoauth_ids_to_use:
                    assigned.device_id = None
            # Now check if any of those to be used are really available and assign them..
            for auth_id_to_use in pogoauth_ids_to_use:
                pogoauth_to_use: Optional[SettingsPogoauth] = all_pogoauth_mapped.get(auth_id_to_use, None)
                if pogoauth_to_use:
                    pogoauth_to_use.device_id = db_entry.device_id
            return True
        elif key == "ggl_login_mail":
            if db_entry.ggl_login_mail:
                # TODO: Get rid of spaghetti by deleting the column
                # First check for an existing assignment, if one is present, set it accordingly
                existing_pogo_auth_assigned_to_device: List[SettingsPogoauth] = await SettingsPogoauthHelper\
                    .get_assigned_to_device(self._session, self._get_instance_id(), db_entry.device_id)
                if existing_pogo_auth_assigned_to_device \
                        and existing_pogo_auth_assigned_to_device[0].username != db_entry.ggl_login_mail:
                    # Device is assigned to another pogoauth google login
                    existing_pogo_auth_assigned_to_device[0].device_id = None

                existing_pogo_auth_with_google_mail: Optional[SettingsPogoauth] = await SettingsPogoauthHelper\
                    .get_google_auth_by_username(self._session, self._get_instance_id(), db_entry.ggl_login_mail)
                if existing_pogo_auth_with_google_mail:
                    # There already is an assignment to this email, this case should not be executed during normal
                    # MADmin usage
                    existing_pogo_auth_with_google_mail.device_id = None
            db_entry.ggl_login_mail = value
            if value:
                # ggl_login_mail is to be set (None is also possible...)
                pogoauth: Optional[SettingsPogoauth] = await SettingsPogoauthHelper \
                    .get_google_auth_by_username(self._session, self._get_instance_id(), value)
                if not pogoauth:
                    # Inconsistency as the pogoauth does not exist
                    return False
                pogoauth.device_id = db_entry.device_id
            return True
        elif key == "walker":
            db_entry.walker_id = int(value)
            return True
        return False

    def _attributes_to_ignore(self) -> Set[str]:
        return {"device_id", "guid"}

    async def _fetch_all_from_db(self, **kwargs) -> Dict[int, Base]:
        return await SettingsDeviceHelper.get_all_mapped(self._session, self._get_instance_id())

    def _resource_info(self, obj: Optional[Base] = None) -> Dict:
        return Device.configuration

    # TODO: '%s/<string:identifier>' optionally at the end of the route
    # TODO: ResourceEndpoint class that loads the identifier accordingly before patch/post etc are called (populate_mode)

    async def post(self) -> web.Response:
        identifier = self.request.match_info.get('identifier', None)
        api_request_data = await self.request.json()
        # TODO: if not identifier
        if self.request.content_type == 'application/json-rpc':
            if not identifier:
                return await self._json_response(self.request.method, status=405)
            device: Optional[SettingsDevice] = await SettingsDeviceHelper.get(self._session, self._get_instance_id(),
                                                                              int(identifier))
            try:
                if not device:
                    return await self._json_response(dict(), status=404)
                call = api_request_data['call']
                args = api_request_data.get('args', {})
                if call == 'device_state':
                    active = args.get('active', 1)
                    self._get_mapping_manager().set_device_state(int(identifier), active)
                    # TODO:..
                    # self._get_mapping_manager().device_set_disabled(device.name)
                    await self._get_ws_server().force_cancel_worker(device.name)
                    return await self._json_response(dict(), status=200)
                elif call == 'flush_level':
                    await TrsVisitedHelper.flush_all_of_origin(self._session, device.name)
                    self._commit_trigger = True
                    return await self._json_response(dict(), status=204)
                else:
                    return await self._json_response(call, status=501)
            except KeyError:
                return await self._json_response("Invalid key found in request.", status=501)
        else:
            return await super().post()

    # TODO: Fetch & create should accept kwargs for primary keys consisting of multiple columns
    async def _fetch_from_db(self, identifier, **kwargs) -> Optional[Base]:
        device: Optional[SettingsDevice] = await SettingsDeviceHelper.get(self._session, self._get_instance_id(),
                                                                          identifier)
        return device

    async def _create_instance(self, identifier):
        device = SettingsDevice()
        device.instance_id = self._get_instance_id()
        device.device_id = identifier
        return device
