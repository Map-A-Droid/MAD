import flask
from threading import current_thread
from mapadroid.madmin.functions import auth_required
from . import apiResponse, apiRequest, apiException, global_variables
from mapadroid.mad_apk import AbstractAPKStorage


class APIHandler(object):
    """ Base handler for API calls

    Args:
        logger (loguru.logger): MADmin debug logger
        app (flask.app): Flask web-app used for MADmin
        api_base (str): Base entrypoint of the api URI
        data_manager (data_manager): Manager for interacting with the datasource
        mapping_manager (mapping_manager): MAD mapping manager
        ws_server (websocketserver): WebSocket server
    """

    def __init__(self, logger, app, api_base, data_manager, mapping_manager, ws_server, config_mode,
                 storage_obj: AbstractAPKStorage, args):
        self._logger = logger
        self._app = app
        self._base = api_base
        self._data_manager = data_manager
        self.dbc = self._data_manager.dbc
        self._mapping_manager = mapping_manager
        self._ws_server = ws_server
        self._config_mode = config_mode
        self.api_req = None
        self.storage_obj = storage_obj
        self._args = args
        self.create_routes()

    def create_routes(self):
        """
        Defines all routes required for the objects.  This must be implemented for each endpoint so the API
        can process requests
        """
        pass

    @auth_required
    def process_request(self, *args, **kwargs):
        """
        Define how to process the API request.  args and kwargs will be populated based off the route requirements

        Returns tuple:
            Response Body
            Response Status Code
            Response kwargs (headers, etc)
        """
        return (None, 501)

    def entrypoint(self, *args, **kwargs):
        """ Processes an API request

        Args:
            endpoint(str): Useless identifier to allow Flask to use a generic function signature
            identifier(str): Identifier for the object to interact with

        Returns:
            Flask.Response
        """
        # Begin processing the request
        self.api_req = apiRequest.APIRequest(self._logger, flask.request)
        current_thread().name = 'madmin-api'
        try:
            self.api_req()
            processed_data = self.process_request(*args, **kwargs)
            try:
                response_data = processed_data[0]
                status_code = processed_data[1]
            except TypeError:
                if processed_data is None:
                    raise
                return processed_data
            try:
                resp_args = processed_data[2]
            except IndexError:
                resp_args = {}
            return apiResponse.APIResponse(self._logger, self.api_req)(response_data, status_code,
                                                                       **resp_args)
        except apiException.ContentException:
            headers = {
                'X-Status': 'Support Content-Types: %s' % (sorted(global_variables.SUPPORTED_FORMATS))
            }
            self._logger.debug2('Invalid content-type received: {}', flask.request.headers.get('Content-Type'))
            return apiResponse.APIResponse(self._logger, self.api_req)(None, 415, headers=headers)
        except apiException.FormattingError as err:
            headers = {
                'X-Status': err.reason
            }
            self._logger.debug2('Formatting error: {}', headers)
            return apiResponse.APIResponse(self._logger, self.api_req)(None, 422, headers=headers)
        except Exception:
            self._logger.opt(exception=True).critical("An unhanded exception occurred!")
            return apiResponse.APIResponse(self._logger, self.api_req)('', 500)
