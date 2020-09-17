from .autoconfHandler import AutoConfHandler
from mapadroid.utils.autoconfig import origin_generator, RGCConfig, PDConfig, AutoConfIssue, AutoConfIssueGenerator
from mapadroid.data_manager.dm_exceptions import UnknownIdentifier


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

    def autoconf_status(self, session_id: int = None):
        sql = "SELECT *\n"\
              "FROM `autoconfig_registration`\n"\
              "WHERE `instance_id` = %s"
        if session_id is None:
            response_data = self.dbc.autofetch_all(sql, (self.dbc.instance_id))
            return (response_data, 200)
        else:
            sql += " AND `session_id` = %s"
            response_data = self.dbc.autofetch_row(sql, (self.dbc.instance_id, session_id))
            if not response_data:
                return (None, 404)
            else:
                return (response_data, 200)

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
            has_auth = self._data_manager.search('pogoauth', params=search)
            if not self._args.autoconfig_no_auth and (not has_auth):
                device = self._data_manager.get_resource('device', update['device_id'])
                try:
                    auth_type = device['settings']['logintype']
                except KeyError:
                    auth_type = 'google'
                # Find one that matches authtype
                sql = "SELECT ag.`account_id`\n"\
                      "FROM `settings_pogoauth` ag\n"\
                      "WHERE ag.`device_id` IS NULL AND ag.`instance_id` = %s AND ag.`login_type` = %s"
                account_id = self.dbc.autofetch_value(sql, (self.dbc.instance_id, auth_type))
                if account_id is None:
                    return ('No configured emails', 400)
                auth = self._data_manager.get_resource('pogoauth', account_id)
                auth['device_id'] = device.identifier
                if is_hopper and auth_type != 'google':
                    auth['login_type'] = auth_type
                auth.save()
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
