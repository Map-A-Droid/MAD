from typing import List, Optional, Tuple

from mapadroid.db.helper.AutoconfigRegistrationHelper import \
    AutoconfigRegistrationHelper
from mapadroid.db.helper.SettingsDeviceHelper import SettingsDeviceHelper
from mapadroid.db.helper.SettingsPogoauthHelper import (LoginType,
                                                        SettingsPogoauthHelper)
from mapadroid.db.model import (AutoconfigRegistration, SettingsDevice,
                                SettingsPogoauth)
from mapadroid.utils.autoconfig import (AutoConfIssue, AutoConfIssueGenerator,
                                        PDConfig, RGCConfig, origin_generator)

from .autoconfHandler import AutoConfHandler


class APIAutoConf(AutoConfHandler):
    component = 'autoconf'
    default_sort = None
    description = 'Interact with AutoConf via MADROM'
    uri_base = 'autoconf'

    def autoconf_config_pd(self):
        conf = PDConfig(self._db_wrapper, self._args)
        try:
            conf.save_config(self.api_req.data)
        except AutoConfIssue as err:
            return err.issues, 400
        return None, 200

    def autoconf_config_rgc(self):
        conf = RGCConfig(self._db_wrapper, self._args)
        try:
            conf.save_config(self.api_req.data)
        except AutoConfIssue as err:
            return err.issues, 400
        return None, 200

    def autoconf_delete_pd(self):
        PDConfig(self._db_wrapper, self._args).delete()
        return None, 200

    def autoconf_delete_rgc(self):
        RGCConfig(self._db_wrapper, self._args).delete()
        return None, 200

    def autoconf_delete_session(self, session_id: int):
        del_info = {
            'session_id': session_id,
            'instance_id': self._db_wrapper.instance_id
        }
        self.dbc.autoexec_delete('autoconfig_registration', del_info)
        return (None, 200)

    def autoconf_status(self, session_id: int = None) -> Tuple[List[AutoconfigRegistration], int]:
        entries: List[AutoconfigRegistration] = await AutoconfigRegistrationHelper.get_all_of_instance(session, instance_id, session_id)
        if len(entries) > 0:
            return entries, 200
        else:
            return [], 404

    def autoconf_set_status(self, session_id: int):
        status = 2
        try:
            if self.api_req.data['status']:
                status = 1
        except KeyError:
            return (None, 400)

        if status == 1:
            is_hopper = False
            ac_issues = AutoConfIssueGenerator(self._db_wrapper, self._args, self.storage_obj)
            if ac_issues.has_blockers():
                return ac_issues.get_issues(), 406, {"headers": ac_issues.get_headers()}
            # Set the device id.  If it was not requested use the origin hopper to create one
            try:
                dev_id = self.api_req.data['device_id'].split('/')[-1]
                # First check if a device entry was created
                device_entry: Optional[SettingsDevice] = await SettingsDeviceHelper.get(session, instance_id, dev_id)
                if not device_entry:
                    return 'Unknown device ID', 400
            except (AttributeError, KeyError):
                hopper_name = 'madrom'
                hopper_response = await origin_generator(session, self._db_wrapper.instance_id, OriginBase=hopper_name)
                if type(hopper_response) != SettingsDevice:
                    return hopper_response
                else:
                    device_entry = hopper_response
                    is_hopper = True
            assigned_to_device: List[SettingsPogoauth] = await SettingsPogoauthHelper.get_assigned_to_device(session,
                                                                                                      instance_id,
                                                                                                      device_entry.device_id)
            if not self._args.autoconfig_no_auth and (not assigned_to_device):
                try:
                    auth_type = LoginType(device_entry.logintype)
                except KeyError:
                    auth_type = LoginType('google')
                # Find one that matches authtype
                unassigned_accounts: List[SettingsPogoauth] = await SettingsPogoauthHelper.get_unassigned(session, instance_id, auth_type)
                if not unassigned_accounts:
                    return 'No configured emails', 400
                auth: SettingsPogoauth = unassigned_accounts.pop()
                auth.device_id = device_entry.device_id
                if is_hopper and auth_type != 'google':
                    auth.login_type = auth_type.value
                session.add(auth)

        await AutoconfigRegistrationHelper.update_status(session, instance_id, session_id, status)
        return None, 200

    def get_config(self, conf_type: str):
        data: dict = {}
        if conf_type == 'rgc':
            data = RGCConfig(self._db_wrapper, self._args).contents
        elif conf_type == 'pd':
            data = PDConfig(self._db_wrapper, self._args).contents
        else:
            return (None, 404)
        return (data, 200)
