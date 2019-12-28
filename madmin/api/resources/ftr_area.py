from . import resource_exceptions
from .resourceHandler import ResourceHandler
from .. import apiHandler

class APIArea(ResourceHandler):
    component = 'area'
    default_sort = 'name'
    description = 'Add/Update/Delete Areas used for Walkers'
    has_rpc_calls = True

    def get_resource_info(self, resource_def):
        if self.mode is None:
            return 'Please specify a mode for resource information.  Valid modes: %s' % (','.join(self.configuration.keys()))
        else:
            return super().get_resource_info(resource_def)

    def post(self, identifier, data, resource_def, resource_info, *args, **kwargs):
        if self.api_req.content_type == 'application/json-rpc':
            try:
                call = self.api_req.data['call']
                args = self.api_req.data.get('args', {})
                if call == 'recalculate':
                    resource = self._data_manager.get_resource('area', identifier=identifier)
                    status = self._mapping_manager.routemanager_recalcualte(resource.identifier)
                    if status:
                        return (None, 204)
                    else:
                        return (None, 409)
                else:
                    return (call, 501)
            except KeyError:
                return (call, 501)
        else:
            return super().post(identifier, data, resource_def, resource_info, *args, **kwargs)

    def populate_mode(self, identifier, method):
        self.mode = self.api_req.headers.get('X-Mode', None)
        if self.mode is None:
            self.mode = self.api_req.params.get('mode', None)
        if self.mode:
            return
        if method in ['GET', 'PATCH']:
            if identifier != None:
                data = self._data_manager.get_resource(self.component, identifier=identifier)
                if data:
                    self.mode = data.area_type
        elif method == 'POST':
            if self.api_req.content_type != 'application/json-rpc':
                raise resource_exceptions.NoModeSpecified()
        elif method == 'PUT':
            raise resource_exceptions.NoModeSpecified()
