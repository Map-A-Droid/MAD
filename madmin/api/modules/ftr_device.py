from .. import apiHandler

class APIDevice(apiHandler.ResourceHandler):
    config_section = 'devices'
    component = 'device'
    default_sort = 'origin'
    description = 'Add/Update/Delete device (Origin) settings'

    configuration = {
        "fields": {
            "origin": {
                "settings": {
                    "type": "text",
                    "require": True,
                    "description": "Name of device (from RGC settings)",
                    "lockonedit": True,
                    "expected": str
                }
            },
            "walker": {
                "settings": {
                    "type": "walkerselect",
                    "require": True,
                    "description": "Walker of this area",
                    "expected": str,
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
                    "expected": str,
                    "uri": True,
                    "data_source": "devicesetting",
                    "uri_source": "api_devicesetting"
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
                    "description": "Delay in seconds after reaching destination. (Default: 2.0)",
                    "expected": float
                }
            },
            "post_teleport_delay": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Delay in seconds after teleport. (Default: 4.0)",
                    "expected": float
                }
            },
            "walk_after_teleport_distance": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Walk in meters to walk after teleport. Might help loading data (Default: None)",
                    "expected": float
                }
            },
            "cool_down_sleep": {
                "settings": {
                    "type": "option",
                    "require": False,
                    "values": [None, False, True],
                    "description": "Add extra cooldown after teleport",
                    "expected": bool
                }
            },
            "post_turn_screen_on_delay": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Delay in seconds after a screenshot has been taken and about to be saved. (Default: 0.2)",
                    "expected": float
                }
            },
            "post_pogo_start_delay": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Delay in seconds to wait after starting pogo. (Default: 60.0)",
                    "expected": float
                }
            },
            "restart_pogo": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Restart Pogo every N location-changes. (Default: 80. - 0 for never)",
                    "expected": float
                }
            },
            "delay_after_hatch": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Delay in minutes to wait before moving to the location of a hatched egg. Raidbosses do not necessarily appear immediately. (Default: 3.5)",
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
                    "description": "Number of seconds to tap the + button when clearing an inventory item. (Default: 3)",
                    "expected": float
                }
            },
            "mitm_wait_timeout": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Timeout in seconds while waiting for data after setting/reaching a location. (Default: 45)",
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
                    "description": "Reboot device if reboot_thresh is reached (Default: false)",
                    "expected": bool
                }
            },
            "reboot_thresh": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Restart device after restart Pogo N times. (Default: 3)",
                    "expected": int
                }
            },
            "restart_thresh": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Restart Pogo after reaching MITM Timeout N times. (Default: 5)",
                    "expected": int
                }
            },
            "post_screenshot_delay": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "The delay in seconds to wait after taking a screenshot to copy it and start the next (Default: 1)",
                    "expected": float
                }
            },
            "screenshot_x_offset": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Adjust the x-axis click offset on devices with softbars and/or black upper bars. (+ right - left / Default: 0)",
                    "expected": int
                }
            },
            "screenshot_y_offset": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Adjust the y-axis click offset on devices with softbars and/or black upper bars. (+ down - up / Default: 0)",
                    "expected": int
                }
            },
            "screenshot_type": {
                "settings": {
                    "type": "option",
                    "require": True,
                    "values": ["jpeg", "png"],
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
            "route_calc_algorithm": {
                "settings": {
                    "type": "option",
                    "values": ["optimized","quick"],
                    "require": False,
                    "description": "Method of calculation for routes. (Default: optimized)",
                    "expected": str
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
                    "values": [False, True],
                    "require": False,
                    "description": "Use this argument if there are login/logout problems with this device or you want to levelup accounts",
                    "expected": bool
                }
            },
            "logintype": {
                "settings": {
                    "type": "option",
                    "values": ["google", "ptc"],
                    "require": False,
                    "description": "Select login type for automatic login. If using Google make sure that account already exists on device.",
                    "expected": str
                }
            },
            "ggl_login_mail": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Declare a login address or domain from device (Empty = first @gmail.com entry)<br>Use | to set more the one account (address|address)",
                    "expected": str
                }
            },
            "ptc_login": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "PTC User/Password (Format username,password)<br>Use | to set more the one account (username,password|username,password)",
                    "expected": str
                }
            },
            "clear_game_data": {
                "settings": {
                    "type": "option",
                    "values": [False, True],
                    "require": False,
                    "description": "Clear game data if logins fail multiple times",
                    "expected": bool
                }
            },
            "account_rotation": {
                "settings": {
                    "type": "option",
                    "values": [False, True],
                    "require": False,
                    "description": "Rotate accounts (f.e. to prevent long cool downs) - Only for PTC",
                    "expected": bool
                }
            },
            "rotation_waittime": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Rotate accounts if wait time is longer than x seconds after teleport (Default: 300 - requires account_rotation to be enabled)",
                    "expected": float
                }
            },
            "rotate_on_lvl_30": {
                "settings": {
                    "type": "option",
                    "values": [False, True],
                    "require": False,
                    "description": "Rotate accounts if player level >= 30 (for leveling mode)",
                    "expected": bool
                }
            },
            "injection_thresh_reboot": {
                 "settings": {
                    "type": "text",
                    "require": False,
                    "empty": None,
                    "description": "Reboot (if enabled) device after not injecting for X times in a row (Default: 20)",
                    "expected": int
                }
            }
        }
    }
