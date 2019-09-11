from .. import apiHandler

class APIAuth(apiHandler.ResourceHandler):
    config_section = 'auth'
    component = 'auth'
    default_sort = 'username'
    description = 'Add/Update/Delete authentication credentials'

    configuration = {
        "name": "auth",
        "fields": {
            "username": {
                "settings": {
                    "type": "text",
                    "require": True,
                    "empty": None,
                    "description": "Username of device",
                    "lockonedit": True,
                "expected": str
                }
            },
            "password": {
                "settings": {
                    "type": "text",
                    "require": True,
                    "empty": None,
                    "description": "Password of device",
                "expected": str
                }
            }
        }
    }

    def validate_dependencies(self):
        # A credential can be removed without causing any issues (other than devices not connecting)
        return True