from typing import Dict, List, Tuple
from .resource import Resource
from mapadroid.data_manager.dm_exceptions import UnknownIdentifier


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

    @classmethod
    def get_avail_accounts(cls, data_manager, auth_type, device_id: int = None) -> Dict[int, Resource]:
        accounts: Dict[int, Resource] = {}
        search = {
            'login_type': auth_type
        }
        pogoauths = data_manager.search('pogoauth', params=search)
        try:
            identifier = int(device_id)
        except (ValueError, TypeError, UnknownIdentifier):
            identifier = None
        # Find all unassigned accounts
        for account_id, account in pogoauths.items():
            if account['device_id'] is not None:
                if identifier is not None and account['device_id'] != identifier:
                    continue
            accounts[account_id] = account
        return accounts

    @classmethod
    def get_avail_devices(cls, data_manager, auth_id: int = None) -> Dict[int, Resource]:
        invalid_devices = []
        avail_devices: Dict[int, Resource] = {}
        device_id: int = None
        pogoauths = data_manager.search('pogoauth')
        try:
            identifier = int(auth_id)
        except (ValueError, TypeError, UnknownIdentifier):
            pass
        else:
            try:
                device_id = pogoauths[identifier]['device_id']
            except KeyError:
                # Auth isn't found. Either it doesnt exist or auth_type mismatch
                return avail_devices
        for pauth_id, pauth in pogoauths.items():
            if pauth['device_id'] is not None and device_id is not None and pauth['device_id'] != device_id:
                invalid_devices.append(pauth['device_id'])
        invalid_devices = list(set(invalid_devices))
        for dev_id, dev in data_manager.get_root_resource('device').items():
            if dev_id in invalid_devices:
                continue
            avail_devices[dev_id] = dev
        return avail_devices

    def get_dependencies(self) -> List[Tuple[str, int]]:
        sql = 'SELECT `device_id` FROM `settings_pogoauth` WHERE `account_id` = %s AND `device_id` IS NOT NULL'
        dependencies = self._dbc.autofetch_column(sql, args=(self.identifier,))
        for ind, device_id in enumerate(dependencies[:]):
            dependencies[ind] = ('device', device_id)
        return dependencies

    def save(self, core_data=None, force_insert=False, ignore_issues=[], **kwargs):
        self.presave_validation(ignore_issues=ignore_issues)
        if self["login_type"] == "google":
            self["username"] = self["username"].lower()
        return super().save(force_insert=force_insert, ignore_issues=ignore_issues)

    def validate_custom(self):
        issues = []
        if 'device_id' in self and self['device_id'] is not None:
            if self['device_id'] not in PogoAuth.get_avail_devices(self._data_manager, auth_id=self.identifier):
                issues.append(("device_id", "PogoAuth not valid for this device"))
        if issues:
            return {
                'issues': issues
            }
