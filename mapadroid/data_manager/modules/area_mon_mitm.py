from .area import Area


class AreaMonMITM(Area):
    area_table = 'settings_area_mon_mitm'
    area_type = 'mon_mitm'
    configuration = {
        "description": "Overlay scanner (MITM) for detecting spawnpoints. Raids will also get detected",
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
                    "empty": False,
                    "description": "Set this option to True, if you scan the area for spawnpoints for the first time",
                    "expected": bool
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
            "coords_spawns_known": {
                "settings": {
                    "type": "option",
                    "require": False,
                    "values": [True, False],
                    "description": "Scan all spawnpoints [true] or just ones with unknown endtimes [false] "
                                   "(Default: True)",
                    "expected": bool
                }
            }
        },
        "settings": {
            "speed": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Speed of player in kmh. This value is used in conjunction with max_distance to "
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
            "delay_after_prio_event": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Offset to be added to events such as spawns or raid starts. E.g. if you want to "
                                   "scan gyms at least a minute after an egg has hatched, set it to 60.  Empty = "
                                   "Disable PrioQ (Default: empty)",
                    "expected": int
                }
            },
            "priority_queue_clustering_timedelta": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Cluster events within the given timedelta in seconds. The latest event in time "
                                   "within a timedelta will be used to scan the clustered events (Default: 300)",
                    "expected": float
                }
            },
            "max_clustering": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Maximum number of prioQ events to cluster (default: unlimited, 0 or empty to set "
                                   "unlimited)",
                    "expected": int
                }
            },
            "remove_from_queue_backlog": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Remove any events from priority queue that have been due for scanning more than "
                                   "the given number of seconds ago. Setting this to 0 can cause a significant backlog "
                                   "buildup, leading to reduced scanning performance. (Default: 300)",
                    "expected": float
                }
            },
            "starve_route": {
                "settings": {
                    "type": "option",
                    "require": False,
                    "values": [None, False, True],
                    "description": "Disable round-robin of route vs. priority queue events. If True, your route may "
                                   "not be completed in time and e.g. only spawns will be scanned (Default: False)",
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
            },
            "include_event_id": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Including event (ID) spawns for route calculation",
                    "expected": int
                }
            }
        }
    }
