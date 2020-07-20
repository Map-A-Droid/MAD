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
                data = {
                    'email': self.api_req.data['email'],
                    'pwd': self.api_req.data['pwd'],
                    'instance_id': self.dbc.instance_id
                }
                status_code = 201
                if email_id:
                    data['email_id'] = email_id
                    status_code = 200
                res = self.dbc.autoexec_insert('autoconfig_google', data, optype="ON DUPLICATE")
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
            if self.api_req.data['status'] is True:
                status = 1
        except KeyError:
            return (None, 400)
        update = {
            'status': status,
            'locked': 1
        }
        has_updates: bool = False
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
                update['device_id'] = dev_id
            except KeyError:
                try:
                    hopper_name = self.api_req.data['origin_hopper']
                except KeyError:
                    hopper_name = 'atv'
                update['name'] = hopper_name
                hopper_response = origin_generator(self._data_manager, self.dbc, OriginBase=hopper_name)
                if type(hopper_response) != tuple:
                    return hopper_response
                else:
                    update['device_id'] = hopper_response[1]
            device = self._data_manager.get_resource('device', update['device_id'])
            # Set the walker for the device
            try:
                walker_id = self.api_req.data['walker_id'].split('/')[-1]
                if walker_id is not None:
                    try:
                        self._data_manager.get_resource('walker', walker_id)
                        update['walker_id'] = walker_id
                        device['walker'] = walker_id
                        has_updates = True
                    except UnknownIdentifier:
                        return ('Unknown walker ID', 400)
            except KeyError:
                pass
            # Set the pool for the device
            try:
                pool_id = self.api_req.data['pool_id'].split('/')[-1]
                if pool_id is not None:
                    try:
                        self._data_manager.get_resource('devicepool', pool_id)
                        update['pool_id'] = pool_id
                        device['pool'] = pool_id
                        has_updates = True
                    except UnknownIdentifier:
                        return ('Unknown pool ID', 400)
            except KeyError:
                pass
            # Changes to the device occurred during this workflow so save the device with the new information
            if has_updates and device:
                device.save()
            # Assign a google account to the box
            try:
                email_id = self.api_req.data['email_id']
                sql = "SELECT `device_id`\n"\
                      "FROM `autoconfig_google`\n"\
                      "WHERE `email_id` = %s AND `instance_id` = %s"
                in_use = self.dbc.autofetch_value(sql, (email_id, self.dbc.instance_id))
                if in_use is not None:
                    return ('Email in-use', 400)
            except KeyError:
                # Auto-assign a google account as one was not specified
                sql = "SELECT `email_id`\n"\
                      "FROM `autoconfig_google`\n"\
                      "WHERE `device_id` IS NULL AND `instance_id` = %s"
                email_id = self.dbc.autofetch_value(sql, (self.dbc.instance_id))
                if email_id is None:
                    return ('No configured emails', 400)
            finally:
                update_info = {
                    'device_id': update['device_id']
                }
                where = {
                    'email_id': email_id,
                    'instance_id': self.dbc.instance_id
                }
                self.dbc.autoexec_update('autoconfig_google', update_info, where_keyvals=where)
        where = {
            'session_id': session_id,
            'instance_id': self.dbc.instance_id
        }
        self.dbc.autoexec_update('autoconfig_registration', update, where_keyvals=where)
        return (None, 200)
