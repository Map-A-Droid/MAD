from .. import dm_exceptions
from . import resource

class Auth(resource.Resource):
    table = 'settings_auth'
    primary_key = 'auth_id'
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
