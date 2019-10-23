from .. import apiHandler


class APIMonList(apiHandler.ResourceHandler):
    config_section = 'monivlist'
    component = 'monivlist'
    default_sort = 'monlist'
    description = 'Add/Update/Delete Pokemon Lists'

    configuration = {
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
                    "require": True,
                    "description": "Encounter these mon ids while walking",
                    "output": "int",
                    "showmonsidpicker": True,
                    "expected": list
                }
            }
        }
    }
