from mapadroid.db.resource_definitions.Resource import Resource


class Walker(Resource):
    # 'settings_walker'
    name_field = 'walkername'
    primary_key = 'walker_id'
    search_field = 'name'
    translations = {
        'walkername': 'name'
    }
    configuration = {
        "fields": {
            "walkername": {
                "settings": {
                    "type": "text",
                    "require": True,
                    "description": "Name of walker",
                    "expected": str
                }
            },
            "setup": {
                "settings": {
                    "type": "list",
                    "require": True,
                    "empty": [],
                    "description": "Order of areas  (Default: Empty List)",
                    "expected": list,
                    "uri": True,
                    "data_source": "walkerarea",
                    "uri_source": "api_walkerarea"
                }
            }
        }
    }
