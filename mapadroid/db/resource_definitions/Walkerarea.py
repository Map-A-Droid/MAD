from mapadroid.db.resource_definitions.Resource import Resource


class Walkerarea(Resource):
    # 'settings_walkerarea'
    name_field = 'walkertext'
    primary_key = 'walkerarea_id'
    search_field = 'name'
    translations = {
        'walkerarea': 'area_id',
        'walkertype': 'algo_type',
        'walkervalue': 'algo_value',
        'walkermax': 'max_walkers',
        'walkertext': 'name',
        'eventid': 'eventid'
    }
    configuration = {
        "fields": {
            "walkerarea": {
                "settings": {
                    "type": "text",
                    "require": True,
                    "description": "Configured area for the walkerarea",
                    "expected": int,
                    "uri": True,
                    "data_source": "area",
                    "uri_source": "api_area"
                }
            },
            "walkertype": {
                "settings": {
                    "type": "text",
                    "require": True,
                    "description": "Mode for the walker",
                    "expected": str
                }
            },
            "walkervalue": {
                "settings": {
                    "type": "text",
                    "require": True,
                    "empty": "",
                    "description": "Value for walkermode.  Please see above how to configure value",
                    "expected": str
                }
            },
            "walkermax": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "empty": "",
                    "description": "Number of walkers than can be in the area.  Empty = 1 worker (Default: Empty)",
                    "expected": int
                }
            },
            "walkertext": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "empty": "",
                    "description": "Human-readable description of the walkerarea",
                    "expected": str
                }
            },
            "eventid": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "empty": "",
                    "description": "internal event id",
                    "expected": int
                }
            }
        }
    }
