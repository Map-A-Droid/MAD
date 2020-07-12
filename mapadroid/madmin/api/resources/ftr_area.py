from mapadroid.madmin.api.resources.resource_exceptions import NoModeSpecified
from .resourceHandler import ResourceHandler


class APIArea(ResourceHandler):
    component = 'area'
    default_sort = 'name'
    description = 'Add/Update/Delete Areas used for Walkers'
    has_rpc_calls = True

    def get_resource_info(self, resource_def):
        if self.mode is None:
            return 'Please specify a mode for resource information.  Valid modes: %s' % (
                ','.join(self.configuration.keys()))
        else:
            return super().get_resource_info(resource_def)

    def post(self, identifier, data, resource_def, resource_info, *args, **kwargs):
        if self.api_req.content_type == 'application/json-rpc':
            try:
                call = self.api_req.data['call']
                args = self.api_req.data.get('args', {})
                if call == 'recalculate':
                    resource = self._data_manager.get_resource('area', identifier=identifier)
                    mode = resource.area_type
                    # iv_mitm is PrioQ driven and idle does not have a route.  This are not recalcable and the returned
                    # status should be representative of that
                    if mode in ['iv_mitm', 'idle']:
                        return ('Unable to recalc mode %s' % (mode,), 422)
                    if resource.recalc_status == 0:
                        # Start the recalculation.  This can take a little bit if the routemanager needs to be started
                        status = self._mapping_manager.routemanager_recalcualte(resource.identifier)
                        if status:
                            return (None, 204)
                        else:
                            # Unable to turn on the routemanager.  Probably should use another error code
                            return (None, 409)
                    else:
                        # Do not allow another recalculation if one is already running.  This value is reset on startup
                        # so it will not be stuck in this state
                        return ('Recalc is already running on this Area', 422)
                else:
                    # RPC not implemented
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
            if identifier is not None:
                data = self._data_manager.get_resource(self.component, identifier=identifier)
                if data:
                    self.mode = data.area_type
        elif method == 'POST':
            if self.api_req.content_type != 'application/json-rpc':
                raise NoModeSpecified()
        elif method == 'PUT':
            raise NoModeSpecified()
