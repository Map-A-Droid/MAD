from typing import List, Tuple
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
            }
        }
    }

    def get_dependencies(self) -> List[Tuple[str, int]]:
        sql = 'SELECT `device_id` FROM `settings_device` WHERE `account_id` = %s'
        dependencies = self._dbc.autofetch_column(sql, args=(self.identifier,))
        for ind, device_id in enumerate(dependencies[:]):
            dependencies[ind] = ('device', device_id)
        return dependencies
