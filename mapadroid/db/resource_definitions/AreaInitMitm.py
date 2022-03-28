class AreaIvMitm:
    configuration = {
        "description": "Init worker for getting location data",
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
            "init_type": {
                "settings": {
                    "type": "option",
                    "values": ['forts', 'mons'],
                    "require": True,
                    "description": "Depending on the type of data to be acquired in the area, either scan for forts or "
                                   "spawnpoints",
                    "expected": str
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
            "init_mode_rounds": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "description": "The amount of rounds to be taken through the area",
                    "expected": int
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
            }
        }
    }
