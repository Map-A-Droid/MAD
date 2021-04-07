from mapadroid.db.resource_definitions.Resource import Resource


class Routecalc(Resource):
    # 'settings_routecalc'
    primary_key = 'routecalc_id'
    configuration = {
        "fields": {
            "routefile": {
                "settings": {
                    "type": "textarea",
                    "require": True,
                    "empty": [],
                    "description": "Route to walk / teleport  (Default: Empty List)",
                    "expected": list
                }
            }
        }
    }
