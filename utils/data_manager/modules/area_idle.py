from . import area

class AreaIdle(area.Area):
    area_table = 'settings_area_idle'
    area_type = 'idle'
    configuration = {
        "description": "Idle Mode - worker do nothing.",
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
                    "expected": str,
                    "uri": True,
                    "data_source": "geofence",
                    "uri_source": "api_geofence"
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
