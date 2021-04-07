from mapadroid.db.resource_definitions.Resource import Resource


class Pogoauth(Resource):
    # 'settings_pogoauth'
    name_field = 'username'
    primary_key = 'account_id'
    search_field = 'username'
    configuration = {
        "fields": {
            "login_type": {
                "settings": {
                    "type": "option",
                    "require": True,
                    "values": ["google", "ptc"],
                    "description": "Account Type",
                    "expected": str
                }
            },
            "username": {
                "settings": {
                    "type": "text",
                    "require": True,
                    "description": "Username",
                    "expected": str
                }
            },
            "password": {
                "settings": {
                    "type": "text",
                    "require": True,
                    "description": "Password",
                    "expected": str
                }
            },
            "device_id": {
                "settings": {
                    "type": "deviceselect",
                    "require": False,
                    "empty": None,
                    "description": "Device assigned to the auth",
                    "expected": int,
                    "uri": True,
                    "data_source": "device",
                    "uri_source": "api_device"
                }
            }
        }
    }
