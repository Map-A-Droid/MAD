from .. import apiHandler, apiResponse, apiRequest, apiException
import threading

class APIRouteCalc(apiHandler.ResourceHandler):
    component = 'routecalc'
    description = 'Add/Update/Delete routecalcs'
    has_rpc_calls = True

    def post(self, identifier, data, resource_def, resource_info, *args, **kwargs):
        resource = resource_def(self._data_manager)
        if self.api_req.content_type == 'application/json-rpc':
            try:
                call = self.api_req.data['call']
                args = self.api_req.data.get('args', {})
                if call == 'recalculate':
                    t = threading.Thread(target=self._mapping_manager.routemanager_recalcualte,args=(args['area_id'],))
                    t.start()
                    return apiResponse.APIResponse(self._logger, self.api_req)(None, 204)
                else:
                    return apiResponse.APIResponse(self._logger, self.api_req)(call, 501)
            except KeyError:
                return apiResponse.APIResponse(self._logger, self.api_req)(call, 501)
        else:
            return super().post(identifier, data, resource_def, resource_info, *args, **kwargs)