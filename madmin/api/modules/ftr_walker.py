from .. import apiHandler

class APIWalker(apiHandler.ResourceHandler):
    component = 'walker'
    default_sort = 'walkername'
    description = 'Add/Update/Delete Walkers'
