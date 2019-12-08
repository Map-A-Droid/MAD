from .. import apiHandler

class APIMonList(apiHandler.ResourceHandler):
    component = 'monivlist'
    default_sort = 'monlist'
    description = 'Add/Update/Delete Pokemon Lists'
