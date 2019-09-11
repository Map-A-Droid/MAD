from .. import apiHandler

class APIMonList(apiHandler.ResourceHandler):
    config_section = 'monlist'
    component = 'monlist'
    description = 'Add/Update/Delete Pokemon Lists (honestly i have no idea)'

    def validate_dependencies(self):
        # TODO - Figure out requirements
        return True