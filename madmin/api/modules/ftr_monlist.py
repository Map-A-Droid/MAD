from .. import apiHandler

class APIMonList(apiHandler.ResourceHandler):
    config_section = 'monivlist'
    component = 'monivlist'
    description = 'Add/Update/Delete Pokemon Lists (honestly i have no idea)'

    configuration = {
        "monivlist": {
            "fields": {
                "monlist": {
                    "settings": {
                        "type": "text",
                        "require": True,
                        "empty": None,
                        "description": "Name of global Monlist",
                        "lockonedit": True,
                        'expected': str
                    }
                },
                "mon_ids_iv": {
                    "settings": {
                        "type": "text",
                        "require": False,
                        "description": "Encounter these mon ids while walking (Put in brackets [1,2,3] as comma separated list!)",
                        "output": "int",
                        "showmonsidpicker": True,
                        "expected": list
                    }
                }
            }
        }
    }

    def validate_dependencies(self):
        # TODO - Figure out requirements
        return True