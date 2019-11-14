from .. import apiHandler

class APIGeofence(apiHandler.ResourceHandler):
    component = 'geofence'
    default_sort = 'name'
    description = 'Add/Update/Delete geofences'
