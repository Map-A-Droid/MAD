from .resourceHandler import ResourceHandler


class APIWalker(ResourceHandler):
    component = 'walker'
    default_sort = 'walkername'
    description = 'Add/Update/Delete Walkers'
