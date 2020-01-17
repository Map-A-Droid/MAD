from .resourceHandler import ResourceHandler


class APIAuth(ResourceHandler):
    component = 'auth'
    default_sort = 'username'
    description = 'Add/Update/Delete authentication credentials'
