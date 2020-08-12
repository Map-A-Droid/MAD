import json
from typing import List, Tuple
from .resource import Resource


class Auth(Resource):
    table = 'settings_auth'
    name_field = 'username'
    primary_key = 'auth_id'
    search_field = 'username'
    configuration = {
        "fields": {
            "username": {
                "settings": {
                    "type": "text",
                    "require": True,
                    "description": "Username of device",
                    "expected": str
                }
            },
            "password": {
                "settings": {
                    "type": "text",
                    "require": True,
                    "description": "Password of device",
                    "expected": str
                }
            }
        }
    }

    def get_dependencies(self) -> List[Tuple[str, int]]:
        sql = 'SELECT `name`, `data` FROM `autoconfig_file` WHERE `instance_id` = %s'
        files = self._dbc.autofetch_all(sql, args=(self._dbc.instance_id,))
        dependencies = []
        for row in files:
            data = json.loads(row['data'])
            if 'mad_auth' not in data:
                continue
            if not data['mad_auth']:
                continue
            if data['mad_auth'] != self.identifier:
                continue
            dependencies.append((f"Used in {row['name']} configuration", 'auth in use'))
        sql = "SELECT `name` FROM `settings_device` WHERE `auth_id` = %s"
        for device in self._dbc.autofetch_column(sql, (self.identifier)):
            dependencies.append((f"Used as override for device {device}", 'auth in use'))
        sql = "SELECT `name` FROM `settings_devicepool` WHERE `auth_id` = %s"
        for pool in self._dbc.autofetch_column(sql, (self.identifier)):
            dependencies.append((f"Used as override for pool {pool}", 'auth in use'))
        return dependencies
