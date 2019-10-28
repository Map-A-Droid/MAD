from .. import apiHandler

class APIWalker(apiHandler.ResourceHandler):
    config_section = 'walker'
    component = 'walker'
    default_sort = 'walkername'
    description = 'Add/Update/Delete Walkers'

    configuration = {
      "fields": {
            "walkername": {
                "settings": {
                    "type": "text",
                    "require": True,
                    "empty": None,
                    "description": "Name of walker",
                    "lockonedit": True,
                    "expected": str
                }
            },
            "setup": {
                "settings": {
                    "type": "list",
                    "require": False,
                    "empty": [],
                    "description": "Order of areas",
                    "lockonedit": False,
                    "expected": list
                }
            }
        }
    }
