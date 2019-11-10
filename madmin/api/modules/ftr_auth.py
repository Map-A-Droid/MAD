from .. import apiHandler

class APIAuth(apiHandler.ResourceHandler):
    config_section = 'auth'
    component = 'auth'
    default_sort = 'username'
    description = 'Add/Update/Delete authentication credentials'
