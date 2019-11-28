from .. import apiHandler

class APIDeviceSetting(apiHandler.ResourceHandler):
    config_section = 'devicesettings'
    component = 'devicesetting'
    default_sort = 'devicepool'
    description = 'Add/Update/Delete Shared device settings'

    configuration = {
        "fields": {
            "devicepool": {
                "settings": {
                    "type": "text",
                    "require": True,
                    "description": "Name for the global device settings",
                    "lockonedit": True,
                "expected": str
                }
            }
        },
        "settings": {
            "post_walk_delay": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Delay in seconds after reaching destination with the speed given. (Default: 2.0)",
                "expected": float
                }
            },
            "post_teleport_delay": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Delay in seconds after a teleport. (Default: 4.0)",
                "expected": float
                }
            },
            "walk_after_teleport_distance": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Walk n seconds after teleport for getting data",
                "expected": float
                }
            },
            "cool_down_sleep": {
                "settings": {
                    "type": "option",
                    "require": False,
                    "values": [False, True],
                    "description": "More cooldown after teleport",
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
                "expected": int
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
                    "description": "Timeout for waiting for data after setting/reaching a location. (Default: 45)",
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
                    "values": [False, True],
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
            "startcoords_of_walker": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Start Coords of Walker (Default: None) (Format: 123.45,67.89)",
                "expected": str
                }
            }
        }
    }
