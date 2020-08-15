from typing import List, Optional, Tuple
from .resource import Resource


class PogoAuth(Resource):
    table = 'settings_pogoauth'
    name_field = 'username'
    primary_key = 'account_id'
    search_field = 'username'
    configuration = {
        "fields": {
            "login_type": {
                "settings": {
                    "type": "option",
                    "require": True,
                    "values": ["google", "ptc"],
                    "description": "Account Type",
                    "expected": str
                }
            },
            "username": {
                "settings": {
                    "type": "text",
                    "require": True,
                    "description": "Username",
                    "expected": str
                }
            },
            "password": {
                "settings": {
                    "type": "text",
                    "require": True,
                    "description": "Password",
                    "expected": str
                }
            },
            "device_id": {
                "settings": {
                    "type": "deviceselect",
                    "require": False,
                    "empty": None,
                    "description": "Device assigned to the auth",
                    "expected": int,
                    "uri": True,
                    "data_source": "device",
                    "uri_source": "api_device"
                }
            }
        }
    }

    def get_dependencies(self) -> List[Tuple[str, int]]:
        sql = 'SELECT `device_id` FROM `settings_device` WHERE `account_id` = %s'
        dependencies = self._dbc.autofetch_column(sql, args=(self.identifier,))
        for ind, device_id in enumerate(dependencies[:]):
            dependencies[ind] = ('device', device_id)
        return dependencies

    def _load(self) -> None:
        super()._load()
        sql = "SELECT `device_id`\n" \
              "FROM `settings_device`\n" \
              "WHERE `account_id` = %s"
        self._data['fields']['device_id'] = self._dbc.autofetch_value(sql, args=(self.identifier))

    def save(self, force_insert: Optional[bool] = False, ignore_issues: Optional[List[str]] = []) -> int:
        self.presave_validation(ignore_issues=ignore_issues)
        device_id = self._data['fields']['device_id']
        core_data = {
            'login_type': self._data['fields']['login_type'],
            'username': self._data['fields']['username'],
            'password': self._data['fields']['password'],
        }
        super().save(core_data=core_data, force_insert=force_insert, ignore_issues=ignore_issues)
        if device_id is not None:
            device = self._data_manager.get_resource('device', device_id)
            device['account_id'] = self.identifier
            device.save()
        else:
            devices = self._data_manager.search('device', params={'account_id': self.identifier})
            if devices:
                device = devices[next(iter(devices))]
                device['account_id'] = None
                device.save()
        return self.identifier

    def validate_custom(self):
        issues = {}
        # One google account per device (for now)
        login_type = None
        try:
            login_type = self._data['fields']['login_type']
        except KeyError:
            return issues
        if login_type == 'google' and \
                ('device_id' in self._data['fields'] and self._data['fields']['device_id']):
            sql = "SELECT `account_id`\n"\
                  "FROM `settings_device`\n"\
                  "WHERE `device_id` = %s"
            aligned = self._dbc.autofetch_column(sql, (self._data['fields']['device_id']))
            if len(aligned) == 1 and any(aligned):
                if aligned[0] != self.identifier:
                    issues['invalid'] = [('device_id', 'Device already has a Google login')]
        return issues
