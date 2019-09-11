from .. import apiHandler

class APIMonList(apiHandler.ResourceHandler):
    config_section = 'monlist'
    component = 'monlist'
    description = 'Add/Update/Delete Pokemon Lists (honestly i have no idea)'

    configuration = {
        "monivlist": {
            "fields": {
                "monlist": {
                    "settings": {
                        "type": "text",
                        "require": "true",
                        "empty": "null",
                        "description": "Name of global Monlist",
                        "lockonedit": "true"
                    }
                },
                "mon_ids_iv": {
                    "settings": {
                        "type": "text",
                        "require": "false",
                        "description": "Encounter these mon ids while walking (Put in brackets [1,2,3] as comma separated list!)",
                        "output": "int",
                        "showmonsidpicker": true
                    }
                }
            }
        }
    }

    def validate_dependencies(self):
        # TODO - Figure out requirements
        return True