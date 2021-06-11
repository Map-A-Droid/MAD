class AreaIvMitm:
    configuration = {
        "description": "IV worker for getting mon values",
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
            "remove_from_queue_backlog": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Remove any events from priority queue that have been due for scanning before NOW "
                                   "- given time in seconds (Default: 0)",
                    "expected": bool
                }
            },
            "starve_route": {
                "settings": {
                    "type": "option",
                    "require": False,
                    "values": [None, False, True],
                    "description": "Disable round-robin of route vs. priority queue events. If True, your route may not"
                                   " be completed in time and e.g. only spawns will be scanned (Default: False)",
                    "expected": bool
                }
            },
            "mon_ids_iv": {
                "settings": {
                    "type": "hidden",
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
            "all_mons": {
                "settings": {
                    "type": "option",
                    "require": False,
                    "values": [False, True],
                    "description":
                        "Dynamically generate the areas IV list to ensure all mons are included. If a mon is not part "
                        "of the IV list it will be appended to the end of the list. Mons will be added in ascending "
                        "order based on their ID.",
                    "expected": bool
                }
            },
            "min_time_left_seconds": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "Ignore mons with less spawn time in seconds (Default: None)",
                    "expected": int
                }
            },
            "encounter_all": {
                "settings": {
                    "type": "option",
                    "require": False,
                    "values": [False, True],
                    "description": "Stay at every location until the device had the chance to encounter all present "
                                   "Pokemon species to reach a near 100% IV-rate. This will slow down route progress!",
                    "expected": bool
                }
            }
        }
    }
