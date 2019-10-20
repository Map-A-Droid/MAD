from .modules import *
from .import apiRequest, apiResponse
import collections
import flask

BASE_URI = '/api'
valid_modules = {
    'area': ftr_area.APIArea,
    'auth': ftr_auth.APIAuth,
    'device': ftr_device.APIDevice,
    'devicesetting': ftr_devicesetting.APIDeviceSetting,
    'monivlist': ftr_monlist.APIMonList,
    'walker': ftr_walker.APIWalker,
    'walkerarea': ftr_walkerarea.APIWalkerArea
}

class APIHandler(object):
    """ Manager for the MADmin API

    Args:
        logger (loguru.logger): MADmin debug logger
        app (flask.app): Flask web-app used for MADmin

    Attributes:
        _app (flask.app): Flask web-app used for MADmin
        _logger: logger (loguru.logger): MADmin debug logger
        _modules (dict): Dictionary of APIHandlers for referring to the other API sections
    """
    def __init__(self, logger, args, app, data_manager):
        self._logger = logger
        self._args = args
        self._app = app
        self._modules = {}
        self._app.route(BASE_URI, methods=['GET'])(self.process_request)
        for mod_name, module in valid_modules.items():
            tmp = module(logger, args, app, BASE_URI, data_manager)
            self._modules[tmp.uri_base] = tmp.description

    def create_routes(self):
        self._app.route(self.uri_base, methods=['GET'], endpoint='api_%s' % (self.component,))(self.process_request)

    def process_request(self):
        """ API call to get data """
        api_req = apiRequest.APIRequest(self._logger, flask.request)
        data = collections.OrderedDict()
        for uri, elem in self._modules.items():
            data[uri] = elem
        return apiResponse.APIResponse(self._logger, api_req)(data, 200)