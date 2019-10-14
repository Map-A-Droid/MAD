import collections
import flask
import json
from madmin.functions import auth_required
from . import apiResponse, apiRequest, apiException
import utils.data_manager


class ResourceHandler(object):
    """ Base handler for API calls

    Args:
        logger (loguru.logger): MADmin debug logger
        args (dict): Arguments used by MADmin during launch
        app (flask.app): Flask web-app used for MADmin
        base (str): Base URI of the API
        data_manager (data_manager): Manager for interacting with the datasource
    """
    config_section = None
    component = None
    iterable = True
    default_sort = None

    def __init__(self, logger, args, app, base, data_manager):
        self._logger = logger
        self._app = app
        self._data_manager = data_manager
        self._base = base
        self._args = args
        self.api_req = None
        if self.component:
            self.uri_base = '%s/%s' % (self._base, self.component)
        else:
            self.uri_base = self._base
        self.create_routes()

    def create_routes(self):
        """ Creates all pertinent routes to for the API resource """
        if self.component:
            route = self.uri_base
            self._app.route(route, methods=['GET', 'POST'], endpoint=self.component)(self.process_request)
            if self.iterable:
                route = '%s/<string:identifier>' % (self.uri_base,)
                self._app.route(route, methods=['DELETE', 'GET', 'PATCH', 'PUT'], endpoint=self.component)(self.process_request)

    def format_data(self, data, config, operation, settings=False):
        save_data = {}
        invalid = []
        missing = []
        for key, val in data.items():
            if type(val) is dict:
                (save_data[key], rec_invalid, rec_missing) = self.format_data(val, config, operation, settings=key.lower() == 'settings')
                invalid += rec_invalid
                missing += rec_missing
            else:
                if settings:
                    entry_def = self.get_def(key, config['settings'])
                else:
                    entry_def = self.get_def(key, config['fields'])
                expected = entry_def['settings'].get('expected', str)
                none_val = entry_def['settings'].get('empty', '')
                formated_val = self.format_value(val, expected, none_val)
                if (formated_val is None or (formated_val and 'len' in dir(formated_val) and len(formated_val) == 0)) and entry_def['settings'].get('require', False):
                    missing.append(key)
                    continue
                try:
                    # We only want to skip the value if its a POST operation.  If not, we want them to be removed from recursive_update
                    if (val is None or (val and 'len' in dir(val) and len(val) == 0)) and settings and operation == 'POST':
                        continue
                    save_data[key] = formated_val
                except Exception:
                    user_readable_types = {
                        str: 'string (MapADroid)',
                        int: 'Integer (1,2,3)',
                        float: 'Decimal (1.0, 1.5)',
                        list: 'Comma-delimited list',
                        bool: 'True|False'
                    }
                    invalid.append('%s:%s' % (key, user_readable_types[expected]))
        return (save_data, invalid, missing)

    def format_value(self, value, expected, none_val):
        try:
            if expected == bool:
                value = True if value.lower() == "true" else False
            elif expected == float:
                value = float(value)
            elif expected == int:
                value = int(value)
            elif expected == str:
                value = value.strip()
        except Exception:
            pass
        if value in ["None", None, ""]:
            return none_val
        return value

    def get_def(self, key, config):
        try:
            return config[key]
        except KeyError:
            pass
        try:
            return config['settings'][key]
        except KeyError:
            pass
        return {'settings': {}} if 'settings' in config else {}

    def get_required_configuration(self, identifier, mode=None):
        if mode and mode in self.configuration:
            return self.configuration[mode]
        if type(self.configuration) is dict and ('fields' in self.configuration or 'settings' in self.configuration):
            return self.configuration

    # =====================================
    # ========= API Functionality =========
    # =====================================
    @auth_required
    def process_request(self, endpoint=None, identifier=None):
        """ Processes an API request

        Args:
            endpoint(str): Useless identifier to allow Flask to use a generic function signature
            identifier(str): Identifier for the object to interact with

        Returns:
            Flask.Response
        """
        # Begin processing the request
        self.api_req = apiRequest.APIRequest(self._logger, flask.request)
        if identifier is None and flask.request.method != 'POST':
            try:
                fetch_all = int(self.api_req.params.get('fetch_all'))
            except:
                fetch_all = 0
            # Use an ordered dict so we can guarantee the order is returned per the class specification
            ordered_data = collections.OrderedDict()
            raw_data = self._data_manager.get_data(self.component, fetch_all=fetch_all)
            if self.default_sort and len(raw_data) > 0:
                if fetch_all == 1:
                    sort_elem = raw_data[list(raw_data.keys())[0]][self.default_sort]
                    if type(sort_elem) == str:
                        sorted_keys = sorted(raw_data, key=lambda x: (raw_data[x][self.default_sort].lower()))
                    else:
                        sorted_keys = sorted(raw_data, key=lambda x: (raw_data[x][self.default_sort]))
                else:
                    sort_elem = raw_data[list(raw_data.keys())[0]]
                    if type(sort_elem) == str:
                        sorted_keys = sorted(raw_data, key=lambda x: (raw_data[x].lower()))
                    else:
                        sorted_keys = sorted(raw_data, key=lambda x: (raw_data[x]))
            else:
                sorted_keys = list(raw_data.keys())
            for key in sorted_keys:
                ordered_data[key] = raw_data[key]
            return apiResponse.APIResponse(self._logger, self.api_req)(ordered_data, 200)
        else:
            if flask.request.method == 'DELETE':
                return self.delete(identifier)
            elif flask.request.method == 'GET':
                return self.get(identifier)
            # Validate incoming data and return any issues
            mode = self.api_req.headers.get('X-Mode', None)
            config = self.get_required_configuration(identifier, mode=mode)
            (self.api_req.data, invalid, missing) = self.format_data(self.api_req.data, config, flask.request.method)
            errors = {}
            if missing:
                errors['missing'] = missing
            if invalid:
                errors['invalid'] = invalid
            if errors:
                return apiResponse.APIResponse(self._logger, self.api_req)(errors, 422)
            try:
                if flask.request.method == 'PATCH':
                    return self.patch(identifier)
                elif flask.request.method == 'POST':
                    return self.post(identifier)
                elif flask.request.method == 'PUT':
                    return self.put(identifier)
            except apiException.APIException as err:
                return apiResponse.APIResponse(self._logger, self.api_req)(err.reason, err.status_code)

    def delete(self, identifier, *args, **kwargs):
        """ API Call to remove data """
        try:
            self._data_manager.delete_data(self.component, identifier=identifier)
        except utils.data_manager.DataManagerDependencyError as err:
            return apiResponse.APIResponse(self._logger, self.api_req)(json.dumps(err.dependencies), 412)
        except KeyError:
            return apiResponse.APIResponse(self._logger, self.api_req)(None, 404)
        else:
            headers = {
                'X-Status': 'Successfully deleted the object'
            }
            return apiResponse.APIResponse(self._logger, self.api_req)(None, 202, headers=headers)

    def get(self, identifier, *args, **kwargs):
        """ API call to get data """
        try:
            return apiResponse.APIResponse(self._logger, self.api_req)(self._data_manager.get_data(self.component, identifier=identifier), 200)
        except KeyError:
            return apiResponse.APIResponse(self._logger, self.api_req)(None, 404)

    def patch(self, identifier, *args, **kwargs):
        """ API call to update data """
        append = self.api_req.headers.get('X-Append')
        try:
            self._data_manager.set_data(self.api_req.data, self.component, 'patch', identifier=identifier, append=append)
        except KeyError:
            return apiResponse.APIResponse(self._logger, self.api_req)(None, 404)
        else:
            headers = {
                'X-Status': 'Successfully updated the object'
            }
            return apiResponse.APIResponse(self._logger, self.api_req)(None, 204, headers=headers)

    def post(self, identifier, *args, **kwargs):
        mode = self.api_req.headers.get('X-Mode')
        try:
            uri_key = self._data_manager.set_data(self.api_req.data, self.component, 'post', mode=mode)
        except utils.data_manager.DataManagerInvalidMode as err:
            return apiResponse.APIResponse(self._logger, self.api_req)('Invalid mode specified: %s' % (err.mode,), 400)
        headers = {
            'Location': uri_key,
            'X-Uri': uri_key,
            'X-Status': 'Successfully created the object'
        }
        return apiResponse.APIResponse(self._logger, self.api_req)(uri_key, 201, headers=headers)

    def put(self, identifier, *args, **kwargs):
        """ API call to replace an object """
        try:
            self._data_manager.set_data(self.api_req.data, self.component, 'put', identifier=identifier,)
        except KeyError:
            headers = {
                'X-Status': 'Object does not exist to update'
            }
            return apiResponse.APIResponse(self._logger, self.api_req)(None, 404, headers=headers)
        else:
            headers = {
                'X-Status': 'Successfully replaced the object'
            }
            return apiResponse.APIResponse(self._logger, self.api_req)(None, 204, headers=headers)
