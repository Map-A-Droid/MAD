from typing import List, Dict, Optional

from aiohttp import web

from mapadroid.db.helper.AutoconfigRegistrationHelper import AutoconfigRegistrationHelper
from mapadroid.db.helper.SettingsDeviceHelper import SettingsDeviceHelper
from mapadroid.db.helper.SettingsPogoauthHelper import SettingsPogoauthHelper, LoginType
from mapadroid.db.model import AutoconfigRegistration, SettingsDevice, SettingsPogoauth
from mapadroid.madmin.AbstractMadminRootEndpoint import AbstractMadminRootEndpoint
from mapadroid.utils.AutoConfIssueGenerator import AutoConfIssueGenerator
from mapadroid.utils.autoconfig import origin_generator


class AutoconfStatusEndpoint(AbstractMadminRootEndpoint):
    async def get(self) -> web.Response:
        # TODO: Ensure int
        session_id: int = self.request.match_info.get('session_id')
        entries: List[AutoconfigRegistration] = await AutoconfigRegistrationHelper \
            .get_all_of_instance(self._session, self._get_instance_id(), session_id)
        if entries:
            return await self._json_response(data=entries)
        else:
            raise web.HTTPNotFound()

    async def post(self) -> web.Response:
        request_body: Dict = await self.request.json()
        status = 2
        try:
            if request_body['status']:
                status = 1
        except KeyError:
            raise web.HTTPBadRequest()

        if status == 1:
            is_hopper = False
            ac_issues = AutoConfIssueGenerator()
            await ac_issues.setup(self._session, self._get_instance_id(), self._get_mad_args(), self._get_storage_obj())
            if ac_issues.has_blockers():
                return await self._json_response(data=ac_issues.get_issues(self.request), status=406,
                                           headers=ac_issues.get_headers())
            # Set the device id.  If it was not requested use the origin hopper to create one
            try:
                dev_id = request_body['device_id'].split('/')[-1]
                # First check if a device entry was created
                device_entry: Optional[SettingsDevice] = await SettingsDeviceHelper.get(self._session,
                                                                                        self._get_instance_id(),
                                                                                        dev_id)
                if not device_entry:
                    return await self._json_response(text="Unknown device ID", status=400)
            except (AttributeError, KeyError):
                hopper_name = 'madrom'
                hopper_response = await origin_generator(self._session, self._get_instance_id(),
                                                         OriginBase=hopper_name)
                if type(hopper_response) != SettingsDevice:
                    return hopper_response
                else:
                    device_entry = hopper_response
                    is_hopper = True
            assigned_to_device: List[SettingsPogoauth] = await SettingsPogoauthHelper \
                .get_assigned_to_device(self._session, self._get_instance_id(), device_entry.device_id)
            if not self._get_mad_args().autoconfig_no_auth and (not assigned_to_device):
                try:
                    auth_type = LoginType(device_entry.logintype)
                except KeyError:
                    auth_type = LoginType('google')
                # Find one that matches authtype
                unassigned_accounts: List[SettingsPogoauth] = await SettingsPogoauthHelper \
                    .get_unassigned(self._session, self._get_instance_id(), auth_type)
                if not unassigned_accounts:
                    return await self._json_response(text="No configured emails", status=400)
                auth: SettingsPogoauth = unassigned_accounts.pop()
                auth.device_id = device_entry.device_id
                if is_hopper and auth_type != 'google':
                    auth.login_type = auth_type.value
                self._session.add(auth)
        # TODO: Ensure int
        session_id: int = self.request.match_info['session_id']
        await AutoconfigRegistrationHelper.update_status(self._session, self._get_instance_id(), session_id, status)
        return await self._json_response()

    async def delete(self) -> web.Response:
        # TODO: Ensure int
        session_id: int = self.request.match_info['session_id']
        await AutoconfigRegistrationHelper.delete(self._session, self._get_instance_id(), session_id)
        return await self._json_response()
