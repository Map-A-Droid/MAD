from .. import apiHandler

class APIDeviceSetting(apiHandler.ResourceHandler):
    component = 'devicepool'
    default_sort = 'devicepool'
    description = 'Add/Update/Delete Shared device settings'
