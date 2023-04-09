from typing import Dict, List, Optional, Union

from aiohttp import web

from mapadroid.db.helper.AutoconfigRegistrationHelper import \
    AutoconfigRegistrationHelper
from mapadroid.db.helper.SettingsDeviceHelper import SettingsDeviceHelper
from mapadroid.db.helper.SettingsPogoauthHelper import (LoginType,
                                                        SettingsPogoauthHelper)
from mapadroid.db.model import (AuthLevel, AutoconfigRegistration,
                                SettingsDevice, SettingsPogoauth)
from mapadroid.madmin.AbstractMadminRootEndpoint import (
    AbstractMadminRootEndpoint, check_authorization_header)
from mapadroid.utils.autoconfig import origin_generator
from mapadroid.utils.AutoConfIssueGenerator import AutoConfIssueGenerator


class AutoconfStatusEndpoint(AbstractMadminRootEndpoint):
    @check_authorization_header(AuthLevel.MADMIN_ADMIN)
    async def get(self) -> web.Response:
        # TODO: Ensure int
        session_id: int = self.request.match_info.get('session_id')
        entries: List[AutoconfigRegistration] = await AutoconfigRegistrationHelper \
            .get_all_of_instance(self._session, self._get_instance_id(), session_id)
        if entries:
            return await self._json_response(data=entries)
        else:
            raise web.HTTPNotFound()

    @check_authorization_header(AuthLevel.MADMIN_ADMIN)
    async def post(self) -> web.Response:
        request_body: Dict = await self.request.json()
        status = 2
        try:
            if request_body['status']:
                status = 1
        except KeyError:
            raise web.HTTPBadRequest()
        device_entry: Optional[SettingsDevice] = None
        if status == 1:
            is_hopper = False
            ac_issues = AutoConfIssueGenerator()
            await ac_issues.setup(self._session, self._get_instance_id(), self._get_mad_args(), self._get_storage_obj())
            if ac_issues.has_blockers():
                return await self._json_response(data=ac_issues.get_issues(self.request), status=406,
                                                 headers=ac_issues.get_headers())
            # Set the device id.  If it was not requested use the origin hopper to create one
            try:
                dev_id = request_body['device_id']
                # First check if a device entry was created
                device_entry: Optional[SettingsDevice] = await SettingsDeviceHelper.get(self._session,
                                                                                        self._get_instance_id(),
                                                                                        dev_id)
                if not device_entry:
                    return await self._json_response(text="Unknown device ID", status=400)
            except (AttributeError, KeyError):
                hopper_name = 'madrom'
                async with self._session.begin_nested() as nested_transaction:
                    hopper_response: Union[SettingsDevice, web.Response] = await origin_generator(self._session,
                                                                                                  self._get_instance_id(),
                                                                                                  OriginBase=hopper_name)
                    if type(hopper_response) != SettingsDevice:
                        return hopper_response
                    else:
                        device_entry = hopper_response
                        await nested_transaction.commit()
            assigned_to_device: Optional[SettingsPogoauth] = await SettingsPogoauthHelper \
                .get_assigned_to_device(self._session, device_entry.device_id)
            if not self._get_mad_args().autoconfig_no_auth and (not assigned_to_device):
                unassigned_accounts: List[SettingsPogoauth] = await SettingsPogoauthHelper \
                    .get_unassigned(self._session, self._get_instance_id(), auth_type=None)
                if not unassigned_accounts:
                    return await self._json_response(text="No configured emails", status=400)
                auth: SettingsPogoauth = unassigned_accounts.pop()
                auth.device_id = device_entry.device_id
                self._save(auth)
        # TODO: Ensure int
        session_id: int = self.request.match_info['session_id']
        autoconf_reg = await AutoconfigRegistrationHelper.update_status(self._session, self._get_instance_id(),
                                                                        session_id, status,
                                                                        device_entry.device_id if device_entry else None)
        if not autoconf_reg:
            raise web.HTTPNotFound()
        self._commit_trigger = True
        return await self._json_response(autoconf_reg)

    @check_authorization_header(AuthLevel.MADMIN_ADMIN)
    async def delete(self) -> web.Response:
        # TODO: Ensure int
        session_id: int = self.request.match_info['session_id']
        await AutoconfigRegistrationHelper.delete(self._session, self._get_instance_id(), session_id)
        self._commit_trigger = True
        return await self._json_response({})
