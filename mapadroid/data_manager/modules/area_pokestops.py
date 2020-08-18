from .area import Area


class AreaPokestops(Area):
    area_table = 'settings_area_pokestops'
    area_type = 'pokestops'
    configuration = {
        "description": "Discover all quests from Pokestops",
        "fields": {
            "name": {
                "settings": {
                    "type": "text",
                    "require": True,
                    "description": "Name of area",
                    "expected": str
                }
            },
            "geofence_included": {
                "settings": {
                    "type": "geofence",
                    "require": True,
                    "description": "Including geofence for scanarea",
                    "expected": int,
                    "uri": True,
                    "data_source": "geofence",
                    "uri_source": "api_geofence"
                }
            },
            "geofence_excluded": {
                "settings": {
                    "type": "geofence",
                    "require": False,
                    "description": "Excluding geofence for scanarea",
                    "expected": int,
                    "uri": True,
                    "data_source": "geofence",
                    "uri_source": "api_geofence"
                }
            },
            "routecalc": {
                "settings": {
                    "type": "hidden",
                    "require": False,
                    "description": "ID of routefile",
                    "expected": int,
                    "uri": True,
                    "data_source": "routecalc",
                    "uri_source": "api_routecalc"
                }
            },
            "init": {
                "settings": {
                    "type": "option",
                    "require": True,
                    "values": [False, True],
                    "empty": False,
                    "description": "Set this option to True, if you scan the area for stops for the first time",
                    "expected": bool
                }
            },
            "level": {
                "settings": {
                    "type": "option",
                    "require": False,
                    "values": [False, True],
                    "description": "Level up an account mode.  (Default: False)",
                    "expected": bool
                }
            },
            "route_calc_algorithm": {
                "settings": {
                    "type": "option",
                    "values": ['route', 'routefree'],
                    "require": False,
                    "description": "Method of calculation for routes. (Default route)",
                    "expected": str
                }
            }
        },
        "settings": {
            "speed": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Speed of player in kmh.  This value is used in conjunction with max_distance to "
                                   "determine if the worker should walk or teleport (Default: 0)",
                    "expected": float
                }
            },
            "max_distance": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Max. distance of walking - If the distance between points is greater than this "
                                   "value the worker will teleport (Default: 0)",
                    "expected": float
                }
            },
            "ignore_spinned_stops": {
                "settings": {
                    "type": "option",
                    "values": [None, True, False],
                    "require": False,
                    "description": "Do not spin stops that have been spun in the past (for level mode) (Default: True)",
                    "expected": bool
                }
            },
            "cleanup_every_spin": {
                "settings": {
                    "type": "option",
                    "values": [None, False, True],
                    "require": False,
                    "description": "Cleanup quest inventory after every stop (Default: False)",
                    "expected": bool
                }
            }
        }
    }
