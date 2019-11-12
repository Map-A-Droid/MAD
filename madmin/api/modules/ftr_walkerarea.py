from .. import apiHandler

class APIWalkerArea(apiHandler.ResourceHandler):
    component = 'walkerarea'
    default_sort = 'walkertext'
    description = 'Add/Update/Delete Area settings used for walkers'
