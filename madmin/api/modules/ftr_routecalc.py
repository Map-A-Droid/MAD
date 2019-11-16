from .. import apiHandler, apiResponse, apiRequest, apiException

class APIRouteCalc(apiHandler.ResourceHandler):
    component = 'routecalc'
    description = 'Add/Update/Delete routecalcs'
    has_rpc_calls = True

    def post(self, identifier, data, resource_def, resource_info, *args, **kwargs):
        resource = resource_def(self._logger, self._data_manager)
        if self.api_req.content_type == 'application/json-rpc':
            try:
                call = self.api_req.data['call']
                args = self.api_req.data.get('args', {})
                if call == 'recalculate':
                    self._mapping_manager.routemanager_recalcualte(args['area_id'])
                    return apiResponse.APIResponse(self._logger, self.api_req)(None, 204)
                else:
                    raise apiResponse.APIResponse(self._logger, self.api_req)(call, 501)
            except KeyError:
                raise apiResponse.APIResponse(self._logger, self.api_req)(call, 501)
        else:
            super().post(identifier, data, resource_def, resource_info, *args, **kwargs)