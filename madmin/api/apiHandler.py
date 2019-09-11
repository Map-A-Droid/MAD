import collections
import flask
import json
from madmin.functions import auth_required, recursive_update
from . import apiResponse, apiRequest, apiException

class ResourceHandler(object):
    """ Base handler for API calls

    Args:
        logger (loguru.logger): MADmin debug logger
        args (dict): Arguments used by MADmin during launch
        app (flask.app): Flask web-app used for MADmin
        base (str): Base URI of the API
        manager (APIHandler): Manager for handling the API calls
    """
    config_section = None
    component = None
    iterable = True
    default_sort = None
    def __init__(self, logger, args, app, base, manager):
        self._logger = logger
        self._app = app
        self._manager = manager
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
                (save_data[key], rec_invalid, rec_missing) = self.format_data(val, config, operation, settings=key.lower()=='settings')
                invalid += rec_invalid
                missing += rec_missing
            else:
                if settings:
                    entry_def = self.get_def(key, config['settings'])
                else:
                    entry_def = self.get_def(key, config['fields'])
                expected = entry_def['settings'].get('expected', str)
                if (val is None or (val and len(val) == 0)) and entry_def['settings'].get('require', False):
                    missing.append(key)
                    continue
                try:
                    # We only want to skip the value if its a POST operation.  If not, we want them to be removed from recursive_update
                    if (val is None or (val and 'len' in dir(val) and len(val) == 0)) and settings and operation == 'POST':
                        continue
                    save_data[key] = self.format_value(val, expected)
                except:
                    user_readable_types = {
                        str: 'string (MapADroid)',
                        int: 'Integer (1,2,3)',
                        float: 'Decimal (1.0, 1.5)',
                        list: 'Comma-delimited list',
                        bool: 'True|False'
                    }
                    invalid.append('%s:%s' % (key, user_readable_types[expected]))
        return (save_data, invalid, missing)

    def format_value(self, value, expected):
        if value in ["None", None]:
            if expected == str:
                return ""
            return None
        elif expected == 'list':
            if '[' in value and ']' in value:
                if ':' in value:
                    tempvalue = []
                    valuearray = value.replace('[', '').replace(']', '').replace(
                        ' ', '').replace("'", '').split(',')
                    for k in valuearray:
                        tempvalue.append(str(k))
                    value = tempvalue
                else:
                    value = list(value.replace('[', '').replace(']', '').split(','))
                    value = [int(i) for i in value]
        elif expected == bool:
            value = True if value.lower() == "true" else False
        elif expected == float:
            value = float(value)
        elif expected == int:
            value = int(value)
        return value

    def generate_uri(self, identifier):
        """ Returns the URI resource from the uri_base """
        return '%s/%s' % (self.uri_base, identifier,)

    def get_def(self, key, config):
        try:
            return config[key]
        except KeyError:
            pass
        try:
            return config['settings'][key]
        except KeyError:
            pass
        return {'settings':{}} if 'settings' in config else {}

    def get_required_configuration(self, identifier, mode=None):
        if mode and mode in self.configuration:
            return self.configuration[mode]
        if type(self.configuration) is dict and ('fields' in self.configuration or 'settings' in self.configuration):
            return self.configuration

    def load_config(self, section=None):
        config = None
        try:
            with open('configs/mappings.json', 'rb') as fh:
                config = json.load(fh)
            if section:
                config = config[section]
        except Exception as err:
            self._logger.warn(err)
        return config

    def lookup_object(self, identifier=None):
        section_data = self.load_config(self.config_section)
        identifier = self.parse_identifier(identifier)
        if identifier is not None:
            return section_data['entries'][identifier]
        else:
            return section_data['entries']

    def parse_identifier(self, identifier):
        if '/' in identifier:
            identifier = identifier[identifier.rfind('/')+1:]
        return identifier

    def save_config(self, config):
        with open(self._args.mappings, 'w') as outfile:
            json.dump(config, outfile, indent=4, sort_keys=True)

    def validate_data(self, **kwargs):
        valid_data = None
        formatting_errors = []
        missing_required_fields = []

    def validate_entry(self, entry, expected):
        pass

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
            # Use an ordered dict so we can guarantee the order is returned per the class specification
            ordered_data = collections.OrderedDict()
            raw_data = self.load_config(self.config_section)['entries']
            if self.default_sort and len(raw_data) > 0:
                sort_elem = raw_data[list(raw_data.keys())[0]][self.default_sort]
                if type(sort_elem) == str:
                    sorted_keys = sorted(raw_data, key=lambda x: (raw_data[x][self.default_sort].lower()))
                else:
                    sorted_keys = sorted(raw_data, key=lambda x: (raw_data[x][self.default_sort]))
            else:
                sorted_keys = list(raw_data.keys())
            for key in sorted_keys:
                ordered_data[self.generate_uri(key)] = raw_data[key]
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
        mapping_data = self.load_config()
        if not self.validate_dependencies():
            headers = {
                'X-Status': 'Failed dependency check'
            }
            return apiResponse.APIResponse(self._logger, self.api_req)(None, 412,  headers=headers)
        try:
            del mapping_data[self.config_section]['entries'][identifier]
        except KerError:
            return apiResponse.APIResponse(self._logger, self.api_req)(None, 404)
        else:
            self.save_config(mapping_data)
            headers = {
                'X-Status': 'Successfully deleted the object'
            }
            return apiResponse.APIResponse(self._logger, self.api_req)(None, 202,  headers=headers)

    def get(self, identifier, *args, **kwargs):
        """ API call to get data """
        try:
            return apiResponse.APIResponse(self._logger, self.api_req)(self.lookup_object(identifier), 200)
        except KeyError:
            return apiResponse.APIResponse(self._logger, self.api_req)(None, 404)

    def patch(self, identifier, *args, **kwargs):
        """ API call to update data """
        mapping_data = self.load_config()
        mode = self.api_req.headers.get('Mode')
        append = self.api_req.headers.get('X-Append')
        try:
            mapping_data[self.config_section]['entries'][identifier] = recursive_update(mapping_data[self.config_section]['entries'][identifier],
                                                                                        self.api_req.data,
                                                                                        append=append)
            self.save_config(mapping_data)
        except KeyError:
            return apiResponse.APIResponse(self._logger, self.api_req)(None, 404)
        else:
            self.save_config(mapping_data)
            headers = {
                'X-Status': 'Successfully updated the object'
            }
            return apiResponse.APIResponse(self._logger, self.api_req)(self.lookup_object(identifier), 204,  headers=headers)

    def post(self, identifier, *args, **kwargs):
        mapping_data = self.load_config()
        mode = self.api_req.headers.get('Mode')
        append = self.api_req.headers.get('X-Append')
        index = str(int(mapping_data[self.config_section]['index']))
        uri_key = self.generate_uri(index)
        mapping_data[self.config_section]['entries'][index] = self.api_req.data
        mapping_data[self.config_section]['index'] = int(index) + 1
        self.save_config(mapping_data)
        headers = {
            'Location': uri_key,
            'X-Uri': uri_key,
            'X-Status': 'Successfully created the object'
        }
        return apiResponse.APIResponse(self._logger, self.api_req)(uri_key, 201, headers=headers)

    def put(self, identifier, *args, **kwargs):
        """ API call to replace an object """
        mapping_data = self.load_config()
        mode = self.api_req.headers.get('Mode')
        append = self.api_req.headers.get('X-Append')
        try:
            mapping_data[self.config_section]['entries'][identifier] = self.api_req.data
        except KeyError:
            headers = {
                'X-Status': err
            }
            return apiResponse.APIResponse(self._logger, self.api_req)(None, 404, headers=headers)
        else:
            self.save_config(mapping_data)
            headers = {
                'X-Status': 'Successfully replaced the object'
            }
            return apiResponse.APIResponse(self._logger, self.api_req)(self.lookup_object(identifier), 204, headers=headers)
