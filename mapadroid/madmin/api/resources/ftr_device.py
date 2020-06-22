from .resourceHandler import ResourceHandler


class APIDevice(ResourceHandler):
    component = 'device'
    default_sort = 'origin'
    description = 'Add/Update/Delete device (Origin) settings'
    has_rpc_calls = True

    def post(self, identifier, data, resource_def, resource_info, *args, **kwargs):
        resource = resource_def(self._data_manager, identifier=identifier)
        if self.api_req.content_type == 'application/json-rpc':
            try:
                call = self.api_req.data['call']
                args = self.api_req.data.get('args', {})
                if call == 'device_state':
                    active = args.get('active', 1)
                    origin = resource['origin']
                    self._data_manager.set_device_state(origin, active)
                    if active == 0:
                        self._mapping_manager.device_set_disabled(origin)
                        self._ws_server.force_disconnect(origin)
                    return (None, 200)
                elif call == 'flush_level':
                    resource.flush_level()
                    return (None, 204)
                else:
                    return (call, 501)
            except KeyError:
                return (call, 501)
        else:
            return super().post(identifier, data, resource_def, resource_info, *args, **kwargs)
