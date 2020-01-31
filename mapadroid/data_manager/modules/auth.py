from .resource import Resource


class Auth(Resource):
    table = 'settings_auth'
    name_field = 'username'
    primary_key = 'auth_id'
    search_field = 'username'
    configuration = {
        "fields": {
            "username": {
                "settings": {
                    "type": "text",
                    "require": True,
                    "description": "Username of device",
                    "expected": str
                }
            },
            "password": {
                "settings": {
                    "type": "text",
                    "require": True,
                    "description": "Password of device",
                    "expected": str
                }
            }
        }
    }
