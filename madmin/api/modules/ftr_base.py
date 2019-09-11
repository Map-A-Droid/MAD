import collections
import flask
from .. import apiHandler
from madmin.functions import auth_required
from .. import apiResponse, global_variables, apiException, apiRequest

class APIACore(apiHandler.ResourceHandler):

    def create_routes(self):
        self._app.route(self.uri_base, methods=['GET'], endpoint=self.component)(self.process_request)

    @auth_required
    def process_request(self, endpoint=None, identifier=None):
        """ API call to get data """
        api_req = apiRequest.APIRequest(self._logger, flask.request)
        data = collections.OrderedDict()
        for key, elem in self._manager._modules.items():
            if key == 'base':
                continue
            data[elem.uri_base] = elem.description
        return apiResponse.APIResponse(self._logger, api_req)(data, 200)