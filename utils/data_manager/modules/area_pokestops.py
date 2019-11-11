from . import area

class AreaPokestops(area.Area):
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
                    "expected": str
                }
            },
            "geofence_excluded": {
                "settings": {
                    "type": "geofence",
                    "require": False,
                    "description": "Excluding geofence for scanarea",
                    "expected": str
                }
            },
            "routecalc": {
                "settings": {
                    "type": "text",
                    "require": True,
                    "description": "Name of routefile",
                    "expected": str
                }
            },
            "init": {
                "settings": {
                    "type": "option",
                    "require": True,
                    "values": [False, True],
                    "description": "Set this open True, if you scan the area for gyms / spawnpoints the first time",
                    "expected": bool
                }
            },
            "level": {
                "settings": {
                    "type": "option",
                    "require": True,
                    "values": [False, True],
                    "description": "Level up an account mode",
                    "expected": bool
                }
            },
            "route_calc_algorithm": {
                "settings": {
                    "type": "option",
                    "values": ['optimized','quick'],
                    "require": False,
                    "description": "Method of calculation for routes. (Default optimized)",
                    "expected": str
                }
            }
        },
        "settings": {
            "speed": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Speed of player in kmh",
                    "expected": float
                }
            },
            "max_distance": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Max. distance of walking - otherwise teleport to new location",
                    "expected": float
                }
            },
            "ignore_spinned_stops": {
                "settings": {
                    "type": "option",
                    "values": [True, False],
                    "require": False,
                    "description": "Do not spinn stops already made in the past (for levelmode)",
                    "expected": bool
                }
            },
            "cleanup_every_spin": {
                "settings": {
                    "type": "option",
                    "values": [False, True],
                    "require": False,
                    "description": "Cleanup quest inventory every spinned stop",
                    "expected": bool
                }
            }
        }
    }