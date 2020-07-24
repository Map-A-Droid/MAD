from .autoconfHandler import AutoConfHandler
from mapadroid.utils.autoconfig import origin_generator, RGCConfig, PDConfig, AutoConfIssue
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
            return (None, 400, {"headers": {'X-Issues': err.issues}})
        return (None, 200)

    def autoconf_config_rgc(self):
        conf = RGCConfig(self.dbc, self._args, self._data_manager)
        try:
            conf.save_config(self.api_req.data)
        except AutoConfIssue as err:
            return (None, 400, {"headers": {'X-Issues': err.issues}})
        return (None, 200)

    def autoconf_delete_session(self, session_id: int):
        del_info = {
            'session_id': session_id,
            'instance_id': self.dbc.instance_id
        }
        self.dbc.autoexec_delete('autoconfig_registration', del_info)
        return (None, 200)

    def autoconf_google(self, method: str, email_id: int):
        if method == 'POST':
            try:
                if email_id is not None:
                    status_code = 200
                    where = {
                        'email_id': email_id,
                        'instance_id': self.dbc.instance_id
                    }
                    res = self.dbc.autoexec_update('autoconfig_google', self.api_req.data, where_keyvals=where)
                else:
                    status_code = 201
                    data = {
                        'email': self.api_req.data['email'],
                        'pwd': self.api_req.data['pwd'],
                        'instance_id': self.dbc.instance_id
                    }
                    res = self.dbc.autoexec_insert('autoconfig_google', data)
                return (res, status_code)
            except KeyError:
                return (None, 400)
        elif method == 'DELETE':
            del_info = {
                'email_id': email_id,
                'instance_id': self.dbc.instance_id
            }
            self.dbc.autoexec_delete('autoconfig_google', del_info)
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
            device = self._data_manager.get_resource('device', update['device_id'])
            if device['email_id'] is None:
                # Auto-assign a google account as one was not specified
                sql = "SELECT ag.`email_id`\n"\
                      "FROM `autoconfig_google` ag\n"\
                      "LEFT JOIN `settings_device` sd ON sd.`email_id` = ag.`email_id`\n"\
                      "WHERE sd.`device_id` IS NULL AND ag.`instance_id` = %s"
                email_id = self.dbc.autofetch_value(sql, (self.dbc.instance_id))
                if email_id is None:
                    return ('No configured emails', 400)
                device['email_id'] = email_id
                device.save()
        where = {
            'session_id': session_id,
            'instance_id': self.dbc.instance_id
        }
        self.dbc.autoexec_update('autoconfig_registration', update, where_keyvals=where)
        return (None, 200)
