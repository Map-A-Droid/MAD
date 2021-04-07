class Auth:
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
