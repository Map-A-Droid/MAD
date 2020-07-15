from .resource import Resource
from mapadroid.utils.logging import get_logger, LoggerEnums, get_origin_logger


logger = get_logger(LoggerEnums.data_manager)


class Device(Resource):
    table = 'settings_device'
    name_field = 'origin'
    primary_key = 'device_id'
    search_field = 'name'
    translations = {
        'origin': 'name',
        'pool': 'pool_id',
        'walker': 'walker_id'
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
            }
        },
        "settings": {
            "post_walk_delay": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Delay in seconds after reaching destination with the speed given (Default: 7.0)",
                    "expected": float
                }
            },
            "post_teleport_delay": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Delay in seconds after teleport (Default: 7.0)",
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
            "delay_after_hatch": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Delay in minutes to wait before moving to the location of a hatched egg. Raidbosses"
                                   " do not necessarily appear immediately. (Default: 3.5)",
                    "expected": float
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
            "inventory_clear_item_amount_tap_duration": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Number of seconds to tap the + button when clearing an inventory item. "
                                   "(Default: 3)",
                    "expected": float
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
                    "values": [None, False, True],
                    "description": "Reboot device if reboot_thresh is reached (Default: False)",
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
                    "values": [None, False, True],
                    "require": False,
                    "description": "Use this argument if there are login/logout problems with this device or you want "
                                   "to levelup accounts  (Default: False)",
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
            "ptc_login": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "PTC User/Password (Format username,password).  Use | to set more the one account "
                                   "(username,password|username,password)",
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

    def _load(self) -> None:
        super()._load()
