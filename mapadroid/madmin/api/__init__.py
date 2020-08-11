import collections

import flask

from . import apiRequest, apiResponse
from .autoconf import ftr_autoconf
from .apks import ftr_mad_apks
from .resources import (ftr_area, ftr_auth, ftr_device, ftr_devicesetting, ftr_geofence, ftr_monlist, ftr_routecalc,
                        ftr_walker, ftr_walkerarea, ftr_pogoauth)

BASE_URI = '/api'
valid_resources = {
    'area': ftr_area.APIArea,
    'auth': ftr_auth.APIAuth,
    'device': ftr_device.APIDevice,
    'devicesetting': ftr_devicesetting.APIDeviceSetting,
    'geofence': ftr_geofence.APIGeofence,
    'monivlist': ftr_monlist.APIMonList,
    'pogoauth': ftr_pogoauth.PoGoAuth,
    'routecalc': ftr_routecalc.APIRouteCalc,
    'walker': ftr_walker.APIWalker,
    'walkerarea': ftr_walkerarea.APIWalkerArea,
    # MAD APKs
    'mad_apks': ftr_mad_apks.APIMadAPK,
    # Autoconfig
    'autoconf': ftr_autoconf.APIAutoConf
}


class APIEntry(object):
    """ Manager for the MADmin API

    Args:
        logger (loguru.logger): MADmin debug logger
        app (flask.app): Flask web-app used for MADmin

    Attributes:
        _app (flask.app): Flask web-app used for MADmin
        _logger: logger (loguru.logger): MADmin debug logger
        _resources (dict): Dictionary of APIHandlers for referring to the other API sections
    """

    def __init__(self, logger, app, data_manager, mapping_manager, ws_server, config_mode, storage_obj, args):
        self._logger = logger
        self._app = app
        self._resources = {}
        self._app.route(BASE_URI, methods=['GET'])(self.process_request)
        for _, module in valid_resources.items():
            tmp = module(logger, app, BASE_URI, data_manager, mapping_manager, ws_server, config_mode, storage_obj,
                         args)
            self._resources[tmp.uri_base] = tmp.description

    def create_routes(self):
        self._app.route(self.uri_base, methods=['GET'], endpoint='api_%s' % (self.component,))(
            self.process_request)

    def process_request(self):
        """ API call to get data """
        api_req = apiRequest.APIRequest(self._logger, flask.request)
        data = collections.OrderedDict()
        for uri, elem in self._resources.items():
            data[uri] = elem
        return apiResponse.APIResponse(self._logger, api_req)(data, 200)
