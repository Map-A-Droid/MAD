from typing import List, Tuple

from mapadroid.data_manager.dm_exceptions import UnknownIdentifier
from mapadroid.db.helper.AutoconfigRegistrationHelper import AutoconfigRegistrationHelper
from mapadroid.db.helper.SettingsPogoauthHelper import LoginType, SettingsPogoauthHelper
from mapadroid.db.model import AutoconfigRegistration, SettingsPogoauth
from mapadroid.utils.autoconfig import (AutoConfIssue, AutoConfIssueGenerator,
                                        PDConfig, RGCConfig, origin_generator)

from .autoconfHandler import AutoConfHandler


class APIAutoConf(AutoConfHandler):
    component = 'autoconf'
    default_sort = None
    description = 'Interact with AutoConf via MADROM'
    uri_base = 'autoconf'

    def autoconf_config_pd(self):
        conf = PDConfig(self.dbc, self._args, self._data_manager)
        try:
            conf.save_config(self.api_req.data)
        except AutoConfIssue as err:
            return (err.issues, 400)
        return (None, 200)

    def autoconf_config_rgc(self):
        conf = RGCConfig(self.dbc, self._args, self._data_manager)
        try:
            conf.save_config(self.api_req.data)
        except AutoConfIssue as err:
            return (err.issues, 400)
        return (None, 200)

    def autoconf_delete_pd(self):
        PDConfig(self.dbc, self._args, self._data_manager).delete()
        return (None, 200)

    def autoconf_delete_rgc(self):
        RGCConfig(self.dbc, self._args, self._data_manager).delete()
        return (None, 200)

    def autoconf_delete_session(self, session_id: int):
        del_info = {
            'session_id': session_id,
            'instance_id': self.dbc.instance_id
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
        update = {
            'status': status
        }
        device = None
        if status == 1:
            is_hopper = False
            ac_issues = AutoConfIssueGenerator(self.dbc, self._data_manager, self._args, self.storage_obj)
            if ac_issues.has_blockers():
                return ac_issues.get_issues(), 406, {"headers": ac_issues.get_headers()}
            # Set the device id.  If it was not requested use the origin hopper to create one
            try:
                dev_id = self.api_req.data['device_id'].split('/')[-1]
                try:
                    self._data_manager.get_resource('device', dev_id)
                    update['device_id'] = dev_id
                except UnknownIdentifier:
                    return ('Unknown device ID', 400)
            except (AttributeError, KeyError):
                hopper_name = 'madrom'
                hopper_response = origin_generator(self._data_manager, self.dbc, OriginBase=hopper_name)
                if type(hopper_response) != tuple:
                    return hopper_response
                else:
                    update['device_id'] = hopper_response[1]
                    is_hopper = True
            search = {
                'device_id': update['device_id']
            }
            # TODO: Replace with SQLAlch
            has_auth = self._data_manager.search('pogoauth', params=search)
            if not self._args.autoconfig_no_auth and (not has_auth):
                device = self._data_manager.get_resource('device', update['device_id'])
                try:
                    auth_type = LoginType(device['settings']['logintype'])
                except KeyError:
                    auth_type = LoginType('google')
                # Find one that matches authtype
                unassigned_accounts: List[SettingsPogoauth] = await SettingsPogoauthHelper.get_unassigned(session, instance_id, auth_type)
                if not unassigned_accounts:
                    return 'No configured emails', 400
                auth: SettingsPogoauth = unassigned_accounts.pop()
                auth.device_id = device.identifier
                if is_hopper and auth_type != 'google':
                    auth.login_type = auth_type.value
                session.add(auth)
        where = {
            'session_id': session_id,
            'instance_id': self.dbc.instance_id
        }
        self.dbc.autoexec_update('autoconfig_registration', update, where_keyvals=where)
        return (None, 200)

    def get_config(self, conf_type: str):
        data: dict = {}
        if conf_type == 'rgc':
            data = RGCConfig(self.dbc, self._args, self._data_manager).contents
        elif conf_type == 'pd':
            data = PDConfig(self.dbc, self._args, self._data_manager).contents
        else:
            return (None, 404)
        return (data, 200)
