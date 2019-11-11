from . import area

class AreaRaidsMITM(area.Area):
    area_table = 'settings_area_raids_mitm'
    area_type = 'raids_mitm'
    configuration = {
        "description": "Overlay scanner (MITM) for detecting raids",
        "fields": {
            "name": {
                "settings": {
                    "type": "text",
                    "require": True,
                    "description": "Name of area",
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
            "including_stops": {
                "settings": {
                    "type": "option",
                    "require": True,
                    "values": [False, True],
                    "description": "Calculate route including stops to catch invasions.",
                    "expected": bool
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
            "delay_after_prio_event": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Offset to be added to events such as spawns or raid starts. E.g. if you want to scan gyms at least a minute after an egg has hatched, set it to 60 (Default: empty)<br>Empty = Disable PrioQ",
                    "expected": int
                }
            },
            "priority_queue_clustering_timedelta": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Cluster events within the given timedelta in seconds. The latest event in time within a timedelta will be used to scan the clustered events (Default: 0)",
                    "expected": float
                }
            },
            "remove_from_queue_backlog": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Remove any events in priority queue that have been due for scanning before NOW - given time in seconds (Default: 0)",
                    "expected": float
                }
            },
            "starve_route": {
                "settings": {
                    "type": "option",
                    "require": False,
                    "values": [False, True],
                    "description": "Disable round-robin of route vs. priority queue events. If True,    your route may not be completed in time and e.g. only spawns will be scanned",
                    "expected": bool
                }
            },
            "init_mode_rounds": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Rounds in Init Mode. (Default: 1)",
                    "expected": int
                }
            },
            "mon_ids_iv": {
                "settings": {
                    "type": "lookup",
                    "display": {
                        "name": "monlist",
                        "section": "monivlist"
                    },
                    "require": False,
                    "description": "IV List Resource",
                    "expected": int,
                    "uri": True,
                    "data_source": "monivlist",
                    "uri_source": "api_monivlist"
                }
            }
        }
    }