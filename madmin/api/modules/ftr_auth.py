from .. import apiHandler

class APIAuth(apiHandler.ResourceHandler):
    component = 'auth'
    default_sort = 'username'
    description = 'Add/Update/Delete authentication credentials'
