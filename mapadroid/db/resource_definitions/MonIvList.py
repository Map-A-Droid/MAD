from mapadroid.db.resource_definitions.Resource import Resource


class MonIvList(Resource):
    # 'settings_monivlist'
    name_field = 'monlist'
    primary_key = 'monlist_id'
    search_field = 'name'
    translations = {
        'monlist': 'name'
    }
    configuration = {
        "fields": {
            "monlist": {
                "settings": {
                    "type": "text",
                    "require": True,
                    "description": "Name of global Monlist",
                    'expected': str
                }
            },
            "mon_ids_iv": {
                "settings": {
                    "type": "text",
                    "require": True,
                    "empty": [],
                    "description": "Encounter these mon ids while walking (Default: Empty List)",
                    "expected": list
                }
            }
        }
    }
