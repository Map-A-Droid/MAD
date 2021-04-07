from mapadroid.db.resource_definitions.Resource import Resource


class Geofence(Resource):
    name_field = 'name'
    primary_key = 'geofence_id'
    search_field = 'name'
    configuration = {
        "fields": {
            "name": {
                "settings": {
                    "type": "text",
                    "require": True,
                    "description": "Name of the geofence",
                    "expected": str
                }
            },
            "fence_type": {
                "settings": {
                    "type": "option",
                    "require": True,
                    "values": ['polygon'],
                    "description": "Type of the geofence",
                    "expected": str
                }
            },
            "fence_data": {
                "settings": {
                    "type": "textarea",
                    "require": True,
                    "empty": [],
                    "description": "Data for the geofence (Default: Empty List)",
                    "expected": list
                }
            }
        }
    }
