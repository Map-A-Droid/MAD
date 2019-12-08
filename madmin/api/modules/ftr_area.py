from .. import apiHandler, apiException
import copy

class APIArea(apiHandler.ResourceHandler):
    component = 'area'
    default_sort = 'name'
    description = 'Add/Update/Delete Areas used for Walkers'

    def get_resource_info(self, resource_def):
        if self.mode is None:
            return 'Please specify a mode for resource information.  Valid modes: %s' % (','.join(self.configuration.keys()))
        else:
            return super().get_resource_info(resource_def)

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
        elif method in ['POST', 'PUT']:
            raise apiException.NoModeSpecified()
