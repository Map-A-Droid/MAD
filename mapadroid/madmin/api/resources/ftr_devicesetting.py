from .resourceHandler import ResourceHandler


class APIDeviceSetting(ResourceHandler):
    component = 'devicepool'
    default_sort = 'devicepool'
    description = 'Add/Update/Delete Shared device settings'
