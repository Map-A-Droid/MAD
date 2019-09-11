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
                    "empty": None,
                    "description": "Configured area for the walkerarea",
                    "lockonedit": False,
                    "expected": str
                }
            },
            "walkertype": {
                "settings": {
                    "type": "text",
                    "require": True,
                    "empty": None,
                    "description": "Mode for the walker",
                    "lockonedit": False,
                    "expected": str
                }
            },
            "walkervalue": {
                "settings": {
                    "type": "text",
                    "require": True,
                    "empty": None,
                    "description": "Value for walkermode.    Please see above how to configure value",
                    "lockonedit": False,
                    "expected": str
                }
            },
            "walkermax": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "empty": None,
                    "description": "Number of walkers than can be in the area",
                    "lockonedit": False,
                    "expected": int
                }
            },
            "walkertext": {
                "settings": {
                    "type": "text",
                    "require": False,
                    "empty": None,
                    "description": "Human-readable description of the walkerarea",
                    "lockonedit": False,
                    "expected": str
                }
            }
        }
    }


    # def post(self, identifier, api_req, *args, **kwargs):
    #     resp = super(APIWalkerArea, self).post(identifier, api_req, *args, **kwargs)
    #     if resp.status_code == 201:
    #         uri = resp.headers.get('X-Uri')
    #         walker_uri = api_req.headers.get('Walker')
    #         if walker_uri and walker_uri.isdigit():
    #             walker_uri = '/api/walker/%s' % (walker_uri,)
    #         # TODO - Come up with a way to perform a patch to update the walker vs handling in JS
    #         self._manager['walker'].put()
    #     return resp

    def validate_dependencies(self):
        # A device can be freely removed without any issues
        return True