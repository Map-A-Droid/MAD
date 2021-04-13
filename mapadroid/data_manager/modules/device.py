import re
from typing import List, Optional

from mapadroid.data_manager.modules.pogoauth import PogoAuth
from mapadroid.utils.logging import LoggerEnums, get_logger, get_origin_logger

from .resource import Resource

logger = get_logger(LoggerEnums.data_manager)
pogoauth_fields = {
    'ggl_login': 'google',
    'ptc_login': 'ptc'
}


class Device(Resource):
    table = 'settings_device'
    name_field = 'origin'
    primary_key = 'device_id'
    search_field = 'name'
    translations = {
        'origin': 'name',
        'pool': 'pool_id',
        'walker': 'walker_id',
    }
    configuration = {
        "fields": {
            "origin": {
                "settings": {
                    "type": "text",
                    "require": True,
                    "description": "Name of device (from RGC settings)",
                    "expected": str
                }
            },
            "walker": {
                "settings": {
                    "type": "walkerselect",
                    "require": True,
                    "description": "Walker of this area",
                    "expected": int,
                    "uri": True,
                    "data_source": "walker",
                    "uri_source": "api_walker"
                }
            },
            "pool": {
                "settings": {
                    "type": "poolselect",
                    "require": False,
                    "empty": None,
                    "description": "Configpool for this area",
                    "expected": int,
                    "uri": True,
                    "data_source": "devicepool",
                    "uri_source": "api_devicepool"
                }
            },
            "adbname": {
                "name": "adbname",
                "settings": {
                    "type": "adbselect",
                    "require": False,
                    "empty": None,
                    "description": "ADB devicename",
                    "expected": str
                }
            },
            "ggl_login": {
                "settings": {
                    "type": "emailselect_google",
                    "require": False,
                    "empty": None,
                    "description": "Assigned Google address",
                    "expected": int,
                    "uri": True,
                    "data_source": "pogoauth",
                    "uri_source": "api_pogoauth"
                }
            },
            "ptc_login": {
                "settings": {
                    "type": "ptcselector",
                    "require": False,
                    "empty": None,
                    "description": "PTC accounts assigned to the device",
                    "expected": list,
                    "uri": True,
                    "data_source": "pogoauth",
                    "uri_source": "api_pogoauth"
                }
            },
            "interface_type": {
                "settings": {
                    "type": "option",
                    "values": ["lan", "wlan"],
                    "require": False,
                    "description": "Interface type to use",
                    "expected": str
                }
            },
            "mac_address": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "MAC address of the device",
                    "expected": str
                }
            }
        },
        "settings": {
            "post_walk_delay": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Delay in seconds after reaching destination with the speed given (Default: 0)",
                    "expected": float
                }
            },
            "post_teleport_delay": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Delay in seconds after teleport (Default: 0)",
                    "expected": float
                }
            },
            "walk_after_teleport_distance": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Walk in meters to walk after teleport. Might help loading data (Default: 0)",
                    "expected": float
                }
            },
            "cool_down_sleep": {
                "settings": {
                    "type": "option",
                    "require": False,
                    "values": [None, False, True],
                    "description": "Add extra cooldown after teleport (Default: False)",
                    "expected": bool
                }
            },
            "post_turn_screen_on_delay": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Delay in seconds after a screenshot has been taken and about to be saved (Default: "
                                   "2.0 / 7.0 - Task Dependent)",
                    "expected": float
                }
            },
            "post_pogo_start_delay": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Delay in seconds to wait after starting pogo (Default: 60.0)",
                    "expected": float
                }
            },
            "restart_pogo": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Restart Pogo every N location-changes (Default: 0.  0 for never)",
                    "expected": int
                }
            },
            "inventory_clear_rounds": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Number of rounds to clear the inventory. (Default: 10)",
                    "expected": int
                }
            },
            "mitm_wait_timeout": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Timeout in seconds while waiting for data after setting/reaching a location. "
                                   "(Default: 45)",
                    "expected": float
                }
            },
            "vps_delay": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Set click delay for pokestop walker (VPS -> local device) (Default: 0)",
                    "expected": float
                }
            },
            "reboot": {
                "settings": {
                    "type": "option",
                    "require": False,
                    "values": [None, True, False],
                    "description": "Reboot device if reboot_thresh is reached (Default: True)",
                    "expected": bool
                }
            },
            "reboot_thresh": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Restart device after restart Pogo N times. This value is doubled when init is "
                                   "active (Default: 3)",
                    "expected": int
                }
            },
            "restart_thresh": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Restart Pogo after reaching MITM Timeout N times. This value is doubled when init "
                                   "is active (Default: 5)",
                    "expected": int
                }
            },
            "post_screenshot_delay": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "The delay in seconds to wait after taking a screenshot to copy it and start the "
                                   "next (Default: 1)",
                    "expected": float
                }
            },
            "screenshot_x_offset": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Adjust the x-axis click offset on devices with softbars and/or black upper bars. "
                                   "(+ right - left / Default: 0)",
                    "expected": int
                }
            },
            "screenshot_y_offset": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Adjust the y-axis click offset on devices with softbars and/or black upper bars. "
                                   "(+ down - up / Default: 0)",
                    "expected": int
                }
            },
            "screenshot_type": {
                "settings": {
                    "type": "option",
                    "require": False,
                    "values": [None, "jpeg", "png"],
                    "description": "Type of screenshot (Default: jpeg)",
                    "expected": str
                }
            },
            "screenshot_quality": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Quality of screenshot (Default: 80)",
                    "expected": int
                }
            },
            "startcoords_of_walker": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Start Coords of Walker (Default: None) (Format: 123.45,67.89)",
                    "expected": str
                }
            },
            "screendetection": {
                "settings": {
                    "type": "option",
                    "values": [None, True, False],
                    "require": False,
                    "description": "Use this argument if there are login/logout problems with this device or you want "
                                   "to levelup accounts  (Default: True)",
                    "expected": bool
                }
            },
            "logintype": {
                "settings": {
                    "type": "option",
                    "values": [None, "google", "ptc"],
                    "require": False,
                    "description": "Select login type for automatic login. If using Google make sure that account "
                                   "already exists on device (Default: google)",
                    "expected": str
                }
            },
            "ggl_login_mail": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Declare a login address or domain from device (Empty = first @gmail.com entry).  "
                                   "Use | to set more the one account (address|address)",
                    "expected": str
                }
            },
            "clear_game_data": {
                "settings": {
                    "type": "option",
                    "values": [None, False, True],
                    "require": False,
                    "description": "Clear game data if logins fail multiple times (Default: False)",
                    "expected": bool
                }
            },
            "account_rotation": {
                "settings": {
                    "type": "option",
                    "values": [None, False, True],
                    "require": False,
                    "description": "Rotate accounts (f.e. to prevent long cool downs) - Only for PTC (Default: False)",
                    "expected": bool
                }
            },
            "rotation_waittime": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Rotate accounts if wait time is longer than x seconds after teleport.  Requires "
                                   "account_rotation to be enabled (Default: 300)",
                    "expected": float
                }
            },
            "rotate_on_lvl_30": {
                "settings": {
                    "type": "option",
                    "values": [None, False, True],
                    "require": False,
                    "description": "Rotate accounts if player level >= 30 (for leveling mode)  (Default: False)",
                    "expected": bool
                }
            },
            "injection_thresh_reboot": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Reboot (if enabled) device after not injecting for X times in a row (Default: 20)",
                    "expected": int
                }
            },
            "enhanced_mode_quest": {
                "settings": {
                    "type": "option",
                    "require": False,
                    "values": [None, False, True],
                    "description": "Activate enhanced quest mode for this device",
                    "expected": bool
                }
            },
            "enhanced_mode_quest_safe_items": {
                "settings": {
                    "type": "select",
                    "require": False,
                    "description": "Undeletable items for enhanced quest mode (Default: 1301, 1401,1402, "
                                   "1403, 1106, 901, 902, 903, 501, 502, 503, 504, 301)",
                    "expected": str
                }
            }
        }
    }

    def flush_level(self) -> None:
        origin_logger = get_origin_logger(logger, origin=self['origin'])
        origin_logger.info('Removing visitation status')
        self._dbc.flush_levelinfo(self['origin'])

    def validate_custom(self) -> Optional[dict]:
        data = self.get_resource(backend=True)
        issues = {
            'invalid': []
        }
        bad_macs = []
        mac_fields = ['mac_address', 'wifi_mac_address']
        for field in mac_fields:
            if field not in data:
                continue
            if data[field] is None:
                continue
            if not re.match("[0-9a-f]{2}([-:])[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$", data[field].lower()):
                bad_macs.append((field, 'Invalid MAC address'))
                continue
            search = {
                field: data[field]
            }
            in_use = self._data_manager.search('device', params=search)
            for dev_id in in_use.keys():
                if dev_id != self.identifier:
                    bad_macs.append((field, 'MAC in use'))
        if bad_macs:
            issues['invalid'] += bad_macs

        if self['ggl_login'] is not None:
            if self['ggl_login'] not in PogoAuth.get_avail_accounts(self._data_manager,
                                                                    auth_type='google',
                                                                    device_id=self.identifier):
                issues['invalid'].append(('ggl_login', 'Invalid Google Account specified'))
        if self['ptc_login'] is not None:
            invalid_ptc = []
            valid_auth = PogoAuth.get_avail_accounts(self._data_manager, 'ptc', device_id=self.identifier)
            for ptc in self['ptc_login']:
                if int(ptc) not in valid_auth:
                    invalid_ptc.append(ptc)
            if invalid_ptc:
                msg = 'Invalid PogoAuth specified [%s]' % ','.join([str(x) for x in invalid_ptc])
                issues['invalid'].append(('ptc_login', msg))
        if any(issues['invalid']):
            return issues

    def _load(self) -> None:
        super()._load()
        self.state = 0
        if self._data_manager.is_device_active(self.identifier):
            self.state = 1
        for field, lookup_val in pogoauth_fields.items():
            search = {
                'device_id': self.identifier,
                'login_type': lookup_val
            }
            logins = self._data_manager.search('pogoauth', params=search)
            if field == 'ptc_login':
                self[field] = list(logins.keys())
            else:
                try:
                    self[field] = next(iter(logins))
                except StopIteration:
                    self[field] = None

    def save(self, force_insert: Optional[bool] = False, ignore_issues: Optional[List[str]] = None) -> int:
        if ignore_issues is None:
            ignore_issues = []
        core_data = self.get_core()
        for field in pogoauth_fields:
            try:
                del core_data[field]
            except KeyError:
                pass
        super().save(core_data=core_data, force_insert=force_insert, ignore_issues=ignore_issues)
        # Clear out old values
        for field, lookup_val in pogoauth_fields.items():
            search = {
                'device_id': self.identifier,
                'login_type': lookup_val
            }
            matched_auths = self._data_manager.search('pogoauth', params=search)
            for auth_id, auth in matched_auths.items():
                if field == 'ggl_login' and self[field] != auth_id:
                    auth['device_id'] = None
                    auth.save()
                elif field == 'ptc_login' and auth_id not in self[field]:
                    auth['device_id'] = None
                    auth.save()
        # Save new auth
        if self['ggl_login'] is not None:
            pogoauth: PogoAuth = self._data_manager.get_resource('pogoauth', self['ggl_login'])
            if pogoauth['device_id'] != self.identifier:
                pogoauth['device_id'] = self.identifier
                pogoauth.save()
        if self['ptc_login']:
            for auth_id in self['ptc_login']:
                pogoauth: PogoAuth = self._data_manager.get_resource('pogoauth', auth_id)
                if pogoauth['device_id'] != self.identifier:
                    pogoauth['device_id'] = self.identifier
                    pogoauth.save()
