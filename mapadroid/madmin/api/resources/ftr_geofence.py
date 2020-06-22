from .resourceHandler import ResourceHandler


class APIGeofence(ResourceHandler):
    component = 'geofence'
    default_sort = 'name'
    description = 'Add/Update/Delete geofences'
