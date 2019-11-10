from .. import apiHandler, apiException
import copy

class APIArea(apiHandler.ResourceHandler):
    component = 'area'
    default_sort = 'name'
    description = 'Add/Update/Delete Areas used for Walkers'

    def get_resource_info(self, config):
        if self.mode is None:
            return 'Please specify a mode for resource information.  Valid modes: %s' % (','.join(self.configuration.keys()))
        else:
            return super().get_resource_info(config)

    def get_required_configuration(self, identifier, method):
        try:
            return copy.deepcopy(self.configuration[self.mode])
        except KeyError:
            if method == 'DELETE':
                return
            if self.mode is not None:
                raise apiException.InvalidMode()
            elif method == 'GET' and identifier is None:
                return
            else:
                raise apiException.InvalidMode()

    def populate_mode(self, identifier, method):
        self.mode = self.api_req.headers.get('X-Mode', None)
        if self.mode is None:
            self.mode = self.api_req.params.get('mode', None)
        if self.mode:
            return
        if method in ['GET', 'PATCH']:
            if identifier != None:
                data = self._data_manager.get_data(self.component, identifier=identifier)
                if data:
                    self.mode = data['mode']
                else:
                    raise apiException.InvalidIdentifier()
        elif method in ['POST', 'PUT']:
            raise apiException.NoModeSpecified()
