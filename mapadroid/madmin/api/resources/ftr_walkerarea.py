from .resourceHandler import ResourceHandler


class APIWalkerArea(ResourceHandler):
    component = 'walkerarea'
    default_sort = 'walkertext'
    description = 'Add/Update/Delete Area settings used for walkers'
