from .. import apiHandler

class APIArea(apiHandler.ResourceHandler):
    config_section = 'areas'
    component = 'area'
    default_sort = 'name'
    description = 'Add/Update/Delete Areas used for Walkers'

    configuration = {
        "mon_mitm": {
            "description": "Overlay scanner (MITM) for detecting spawnpoints. Raids will also get detected",
            "fields": {
                "name": {
                    "settings": {
                        "type": "text",
                        "require": True,
                        "description": "Name of area",
                        "lockonedit": True,
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
                        "type": "text",
                        "require": True,
                        "empty": None,
                        "description": "Including geofence for scanarea",
                        "expected": str
                    }
                },
                "geofence_excluded": {
                    "settings": {
                        "type": "text",
                        "require": False,
                        "empty": None,
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
                "coords_spawns_known": {
                    "settings": {
                        "type": "option",
                        "require": True,
                        "values": [True, False],
                        "description": "Scan all spawnpoints or just ones with unknown endtimes",
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
                        "output": int,
                        "expected": float
                    }
                },
                "max_distance": {
                    "settings": {
                        "type": "text",
                        "require": False,
                        "description": "Max. distance of walking - otherwise teleport to new location",
                        "output": int,
                        "expected": float
                    }
                },
                "delay_after_prio_event": {
                    "settings": {
                        "type": "text",
                        "require": False,
                        "description": "Offset to be added to events such as spawns or raid starts. E.g. if you want to scan gyms at least a minute after an egg has hatched, set it to 60 (Default: empty)<br>Empty = Disable PrioQ",
                        "output": int,
                        "expected": int
                    }
                },
                "priority_queue_clustering_timedelta": {
                    "settings": {
                        "type": "text",
                        "require": False,
                        "description": "Cluster events within the given timedelta in seconds. The latest event in time within a timedelta will be used to scan the clustered events (Default: 0)",
                        "output": int,
                        "expected": float
                    }
                },
                "remove_from_queue_backlog": {
                    "settings": {
                        "type": "text",
                        "require": False,
                        "description": "Remove any events in priority queue that have been due for scanning before NOW - given time in seconds (Default: 0)",
                        "output": int,
                        "expected": float
                    }
                },
                "starve_route": {
                    "settings": {
                        "type": "option",
                        "require": False,
                        "values": [False, True],
                        "description": "Disable round-robin of route vs. priority queue events. If True,    your route may not be completed in time and e.g. only spawns will be scanned",
                        "output": int,
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
                        "description": "Select global mon list",
                        "output": int,
                        "showmonsidpicker": True,
                        "expected": "list"
                    }
                },
                "min_time_left_seconds": {
                    "settings": {
                        "type": "text",
                        "require": False,
                        "description": "Ignore mons with less spawntime in seconds",
                        "output": int,
                        "expected": int
                    }
                }
            }
        },
        "iv_mitm": {
            "description": "IV worker for getting mon values",
            "fields": {
                "name": {
                    "settings": {
                        "type": "text",
                        "require": True,
                        "description": "Name of area",
                        "lockonedit": True,
                        "expected": str
                    }
                },
                "geofence_included": {
                    "settings": {
                        "type": "text",
                        "require": True,
                        "empty": None,
                        "description": "Including geofence for scanarea",
                        "expected": str
                    }
                },
                "geofence_excluded": {
                    "settings": {
                        "type": "text",
                        "require": False,
                        "empty": None,
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
                }
            },
            "settings": {
                "speed": {
                    "settings": {
                        "type": "text",
                        "require": False,
                        "description": "Speed of player in kmh",
                        "output": int,
                        "expected": float
                    }
                },
                "max_distance": {
                    "settings": {
                        "type": "text",
                        "require": False,
                        "description": "Max. distance of walking - otherwise teleport to new location",
                        "output": int,
                        "expected": float
                    }
                },
                "delay_after_prio_event": {
                    "settings": {
                        "type": "text",
                        "require": False,
                        "description": "Offset to be added to events such as spawns or raid starts. E.g. if you want to scan gyms at least a minute after an egg has hatched, set it to 60 (Default: empty)<br>Empty = Disable PrioQ",
                        "output": int,
                        "expected": int
                    }
                },
                "priority_queue_clustering_timedelta": {
                    "settings": {
                        "type": "text",
                        "require": False,
                        "description": "Cluster events within the given timedelta in seconds. The latest event in time within a timedelta will be used to scan the clustered events (Default: 300)",
                        "output": int,
                        "expected": float
                    }
                },
                "remove_from_queue_backlog": {
                    "settings": {
                        "type": "text",
                        "require": False,
                        "description": "Remove any events from priority queue that have been due for scanning before NOW - given time in seconds (Default: 0)",
                        "output": int,
                        "expected": bool
                    }
                },
                "starve_route": {
                    "settings": {
                        "type": "option",
                        "require": False,
                        "values": [False, True],
                        "description": "Disable round-robin of route vs. priority queue events. If True,    your route may not be completed in time and e.g. only spawns will be scanned",
                        "output": int,
                        "expected": bool
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
                        "description": "Select global mon list",
                        "output": int,
                        "showmonsidpicker": True,
                        "expected": list
                    }
                },
                "min_time_left_seconds": {
                    "settings": {
                        "type": "text",
                        "require": False,
                        "description": "Ignore mons with less spawntime in seconds",
                        "output": int,
                        "expected": int
                    }
                }
            }
        },
        "pokestops": {
            "description": "Discover all quests from Pokestops",
            "fields": {
                "name": {
                    "settings": {
                        "type": "text",
                        "require": True,
                        "description": "Name of area",
                        "lockonedit": True,
                        "expected": str
                    }
                },
                "geofence_included": {
                    "settings": {
                        "type": "text",
                        "require": True,
                        "empty": None,
                        "description": "Including geofence for scanarea",
                        "expected": str
                    }
                },
                "geofence_excluded": {
                    "settings": {
                        "type": "text",
                        "require": False,
                        "empty": None,
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
                        "output": int,
                        "expected": float
                    }
                },
                "max_distance": {
                    "settings": {
                        "type": "text",
                        "require": False,
                        "description": "Max. distance of walking - otherwise teleport to new location",
                        "output": int,
                        "expected": float
                    }
                },
                "ignore_spinned_stops": {
                    "settings": {
                        "type": "option",
                        "values": [True, False],
                        "require": False,
                        "description": "Do not spinn stops already made in the past (for levelmode)",
                        "output": int,
                        "expected": bool
                    }
                },
                "cleanup_every_spin": {
                    "settings": {
                        "type": "option",
                        "values": [False, True],
                        "require": False,
                        "description": "Cleanup quest inventory every spinned stop",
                        "output": int,
                        "expected": bool
                    }
                }
            }
        },
        "raids_mitm": {
            "description": "Overlay scanner (MITM) for detecting raids",
            "fields": {
                "name": {
                    "settings": {
                        "type": "text",
                        "require": True,
                        "description": "Name of area",
                        "lockonedit": True,
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
                        "type": "text",
                        "require": True,
                        "empty": None,
                        "description": "Including geofence for scanarea",
                        "expected": str
                    }
                },
                "geofence_excluded": {
                    "settings": {
                        "type": "text",
                        "require": False,
                        "empty": None,
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
                        "output": int,
                        "expected": int
                    }
                },
                "priority_queue_clustering_timedelta": {
                    "settings": {
                        "type": "text",
                        "require": False,
                        "description": "Cluster events within the given timedelta in seconds. The latest event in time within a timedelta will be used to scan the clustered events (Default: 0)",
                        "output": int,
                        "expected": float
                    }
                },
                "remove_from_queue_backlog": {
                    "settings": {
                        "type": "text",
                        "require": False,
                        "description": "Remove any events in priority queue that have been due for scanning before NOW - given time in seconds (Default: 0)",
                        "output": int,
                        "expected": float
                    }
                },
                "starve_route": {
                    "settings": {
                        "type": "option",
                        "require": False,
                        "values": [False, True],
                        "description": "Disable round-robin of route vs. priority queue events. If True,    your route may not be completed in time and e.g. only spawns will be scanned",
                        "output": int,
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
                        "description": "Select global mon list",
                        "output": int,
                        "showmonsidpicker": True,
                        "expected": "list"
                    }
                }
            }
        },
        "idle": {
            "description": "Idle Mode - worker do nothing.",
            "fields": {
                "name": {
                    "settings": {
                        "type": "text",
                        "require": True,
                        "description": "Name of area",
                        "lockonedit": True,
                        "expected": str
                    }
                },
                "geofence_included": {
                    "settings": {
                        "type": "text",
                        "require": True,
                        "empty": None,
                        "description": "Including geofence for scanarea",
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
                }
            }
        }
        # "raids_ocr": {
        #     "description": "OCR scanner for detecting raids.",
        #     "fields": {
        #         "name": {
        #             "settings": {
        #                 "type": "text",
        #                 "require": True,
        #                 "description": "Name of area",
        #                 "lockonedit": True,
        #                 "expected": str
        #             }
        #         },
        #         "geofence_included": {
        #             "settings": {
        #                 "type": "text",
        #                 "require": True,
        #                 "empty": None,
        #                 "description": "Including geofence for scanarea",
        #                 "expected": str
        #             }
        #         },
        #         "geofence_excluded": {
        #             "settings": {
        #                 "type": "text",
        #                 "require": False,
        #                 "empty": None,
        #                 "description": "Excluding geofence for scanarea",
        #                 "expected": str
        #             }
        #         },
        #         "routecalc": {
        #             "settings": {
        #                 "type": "text",
        #                 "require": True,
        #                 "description": "Name of routefile",
        #                 "expected": str
        #             }
        #         }
        #     },
        #     "settings": {
        #         "speed": {
        #             "settings": {
        #                 "type": "text",
        #                 "require": True,
        #                 "description": "Speed of player in kmh",
        #                 "expected": float
        #             }
        #         },
        #         "max_distance": {
        #             "settings": {
        #                 "type": "text",
        #                 "require": True,
        #                 "description": "Max. distance of walking - otherwise teleport to new location",
        #                 "expected": float
        #             }
        #         },
        #         "delay_after_prio_event": {
        #             "settings": {
        #                 "type": "text",
        #                 "require": False,
        #                 "description": "Offset to be added to events such as spawns or raid starts. E.g. if you want to scan gyms at least a minute after an egg has hatched, set it to 60 (Default: empty)<br>Empty = Disable PrioQ",
        #                 "output": int,
        #                 "expected": int
        #             }
        #         },
        #         "priority_queue_clustering_timedelta": {
        #             "settings": {
        #                 "type": "text",
        #                 "require": False,
        #                 "description": "Cluster events within the given timedelta in seconds. The latest event in time within a timedelta will be used to scan the clustered events (Default: 0)",
        #                 "output": int,
        #                 "expected": float
        #             }
        #         },
        #         "remove_from_queue_backlog": {
        #             "settings": {
        #                 "type": "text",
        #                 "require": False,
        #                 "description": "Remove any events in priority queue that have been due for scanning before NOW - given time in seconds (Default: 0)",
        #                 "output": int,
        #                 "expected": float
        #             }
        #         },
        #         "starve_route": {
        #             "settings": {
        #                 "type": "option",
        #                 "require": False,
        #                 "values": [False, True],
        #                 "description": "Disable round-robin of route vs. priority queue events. If True,    your route may not be completed in time and e.g. only spawns will be scanned",
        #                 "output": int,
        #                 "expected": bool
        #             }
        #         }
        #     }
        # }
    }
