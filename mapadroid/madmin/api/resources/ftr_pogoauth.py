from .resourceHandler import ResourceHandler


class PoGoAuth(ResourceHandler):
    component = 'pogoauth'
    default_sort = 'username'
    description = 'Add/Update/Delete PoGo credentials'
