from .. import apiHandler
import flask

class APIWalkerArea(apiHandler.ResourceHandler):
    config_section = 'walkerarea'
    component = 'walkerarea'
    default_sort = None
    description = 'Add/Update/Delete Area settings used for walkers'

    configuration = {
        "fields": {
            "walkerarea": {
                "settings": {
                    "type": "text",
                    "require": True,
                    "description": "Configured area for the walkerarea",
                    "lockonedit": False,
                    "expected": str,
                    "uri": True,
                    "data_source": "area",
                    "uri_source": "api_area"
                }
            },
            "walkertype": {
                "settings": {
                    "type": "text",
                    "require": True,
                    "description": "Mode for the walker",
                    "lockonedit": False,
                    "expected": str
                }
            },
            "walkervalue": {
                "settings": {
                    "type": "text",
                    "require": True,
                    "empty": "",
                    "description": "Value for walkermode.    Please see above how to configure value",
                    "lockonedit": False,
                    "expected": str
                }
            },
            "walkermax": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "empty": "",
                    "description": "Number of walkers than can be in the area",
                    "lockonedit": False,
                    "expected": int
                }
            },
            "walkertext": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "empty": "",
                    "description": "Human-readable description of the walkerarea",
                    "lockonedit": False,
                    "expected": str
                }
            }
        }
    }
