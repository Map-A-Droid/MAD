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
            },
            "auth_level": {
                "settings": {
                    "type": "select",
                    "expected": int,
                    "require": True,
                    "description": "The permissions for the credentials. MADMIN allows full access to the settings!"
                }
            }
        }
    }
