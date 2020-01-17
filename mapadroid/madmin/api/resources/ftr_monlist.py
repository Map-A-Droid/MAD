from .resourceHandler import ResourceHandler


class APIMonList(ResourceHandler):
    component = 'monivlist'
    default_sort = 'monlist'
    description = 'Add/Update/Delete Pokemon Lists'
