from .modules import *

BASE_URI = '/api'
valid_modules = {
    'base': ftr_base.APIACore,
    'areas': ftr_area.APIArea,
    'auth': ftr_auth.APIAuth,
    'devices': ftr_device.APIDevice,
    'devicesettings': ftr_devicesetting.APIDeviceSetting,
    'monlist': ftr_monlist.APIMonList,
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
    def __init__(self, logger, args, app):
        self._logger = logger
        self._args = args
        self._app = app
        self._modules = {}
        for mod_name, module in valid_modules.items():
            self._modules[mod_name] = module(logger, args, app, BASE_URI, self)

    def __getitem__(self, key):
        """ Used to access API modules """
        return self._modules[key]
