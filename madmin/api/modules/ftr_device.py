from .. import apiHandler

class APIDevice(apiHandler.ResourceHandler):
    component = 'device'
    default_sort = 'origin'
    description = 'Add/Update/Delete device (Origin) settings'
