import collections
import copy
import re
import flask
from mapadroid.madmin.functions import auth_required
from mapadroid.data_manager.dm_exceptions import (
    UnknownIdentifier,
    ModeNotSpecified,
    ModeUnknown,
    UpdateIssue,
    DependencyError,
    SaveIssue,
    InvalidSection
)
from mapadroid.madmin.api.resources.resource_exceptions import NoModeSpecified
from mapadroid.data_manager.modules import MAPPINGS
from .. import apiHandler


class ResourceHandler(apiHandler.APIHandler):
    """ Base handler for API calls for configuration calls """
    component = None
    iterable = True
    default_sort = None
    mode = None
    has_rpc_calls = False

    def create_routes(self):
        """ Creates all pertinent routes to for the API resource """
        if self.component:
            self.uri_base = '%s/%s' % (self._base, self.component)
        else:
            self.uri_base = self._base
        if self.component:
            route = self.uri_base
            self._app.route(route, methods=['GET', 'POST'], endpoint='api_%s' % (self.component,))(
                self.entrypoint)
            if self.iterable:
                route = '%s/<string:identifier>' % (self.uri_base,)
                methods = ['DELETE', 'GET', 'PATCH', 'PUT']
                if self.has_rpc_calls:
                    methods.append('POST')
                self._app.route(route, methods=methods, endpoint='api_%s' % (self.component,))(
                    self.entrypoint)

    def get_resource_data_root(self, resource_def, resource_info):
        try:
            fetch_all = int(self.api_req.params.get('fetch_all'))
        except TypeError:
            fetch_all = 0
        try:
            hide_resource = int(self.api_req.params.get('hide_resource', 0))
        except TypeError:
            hide_resource = 0
        link_disp_field = self.api_req.params.get('link_disp_field', self.default_sort)
        raw_data = {}
        if fetch_all:
            raw_data = self._data_manager.get_root_resource(self.component)
        else:
            raw_data = self._data_manager.search(self.component, resource_def=resource_def,
                                                 resource_info=resource_info, params=self.api_req.params)
        api_response_data = collections.OrderedDict()
        key_translation = '%s/%%s' % (flask.url_for('api_%s' % (self.component,)))
        if resource_def.configuration:
            for key, value in raw_data.items():
                api_response_data[key_translation % key] = self.translate_data_for_response(value)
        else:
            for key, value in raw_data.items():
                api_response_data[key_translation % key] = value
        if not fetch_all and link_disp_field is not None:
            for key, value in api_response_data.items():
                try:
                    api_response_data[key] = value[link_disp_field]
                except KeyError:
                    # TODO - Return an exception or just return basic?
                    if self.default_sort:
                        api_response_data[key] = value[self.default_sort]
        if hide_resource:
            response_data = api_response_data
        else:
            response_data = {
                'resource': resource_info,
                'results': api_response_data
            }
        return (response_data, 200)

    def get_resource_info(self, resource_def):
        resource = {
            'fields': []
        }
        try:
            resource['fields'] = self.get_resource_info_elems(resource_def.configuration['fields'])
        except KeyError:
            pass
        try:
            resource['settings'] = self.get_resource_info_elems(resource_def.configuration['settings'])
        except KeyError:
            pass
        return resource

    def get_resource_info_elems(self, config, skip_fields=[]):
        variables = []
        for key, field in config.items():
            if key in skip_fields:
                continue
            settings = field['settings']
            field_data = {
                'name': key,
                'descr': settings['description'],
                'required': settings['require'],
            }
            try:
                field_data['values'] = settings['values']
            except KeyError:
                pass
            variables.append(field_data)
        return variables

    # Mode does not exist for basic configuration
    def populate_mode(self, identifier, method):
        pass

    def translate_data_for_datamanager(self, data, config, section=None):
        valid_data = {}
        if section is None:
            working_conf = config.configuration['fields']
        else:
            working_conf = config.configuration['settings']
        for key, value in data.items():
            if key == 'settings':
                valid_data[key] = self.translate_data_for_datamanager(value, config, section='settings')
                continue
            try:
                entity = working_conf[key]['settings']
                if 'uri' in entity:
                    if entity['uri'] is not True:
                        valid_data[key] = value
                    elif value:
                        regex = re.compile(r'%s/(\d+)' % (flask.url_for(entity['uri_source'])))
                        check = value
                        if type(value) is str:
                            check = [value]
                        uri = []
                        for elem in check:
                            match = regex.match(elem)
                            if not match:
                                continue
                            identifier = str(match.group(1))
                            uri.append(identifier)
                        if type(value) is str and len(uri) > 0:
                            value = uri.pop(0)
                        elif type(value) is list:
                            value = uri
                        valid_data[key] = value
                    else:
                        valid_data[key] = value
            except KeyError:
                # Ruh-roh, that key doesnt exist!  Let the data_manager handle it
                valid_data[key] = value
            else:
                valid_data[key] = value
        return valid_data

    def translate_data_for_response(self, data, config=None):
        valid_data = {}
        if config is None:
            config = data.configuration['fields']
        # Process fields
        for key, value in data.items():
            if key == 'settings':
                valid_data[key] = self.translate_data_for_response(value, config=data.configuration['settings'])
                continue
            try:
                entity = config[key]['settings']
            except KeyError:
                # Probably a 'fake' field.  Add it and continue
                valid_data[key] = value
                continue
            if value is not None:
                try:
                    if entity['uri'] is not True:
                        valid_data[key] = value
                        continue
                    uri = '%s/%%s' % (flask.url_for(entity['uri_source']),)
                    if type(value) == list:
                        valid = []
                        for elem in value:
                            valid.append(uri % elem)
                        valid_data[key] = valid
                    else:
                        valid_data[key] = uri % str(value)
                except KeyError:
                    valid_data[key] = value
            else:
                # TODO - Determine this
                # Honestly I am not sure if we should just skip or return the empty value
                try:
                    empty = entity['empty']
                    if empty is not None:
                        valid_data[key] = empty
                except KeyError:
                    continue
        return valid_data

    # =====================================
    # ========= API Functionality =========
    # =====================================
    @auth_required
    def process_request(self, *args, **kwargs):
        """ Processes an API request

        Args:
            endpoint(str): Useless identifier to allow Flask to use a generic function signature
            identifier(str): Identifier for the object to interact with

        Returns:
            Flask.Response
        """
        # Begin processing the request
        try:
            identifier = kwargs.get('identifier', None)
            self.populate_mode(identifier, flask.request.method)
            if flask.request.method == 'DELETE':
                return self.delete(identifier)
            try:
                resource_def = self._data_manager.get_resource_def(self.component, mode=self.mode)
                resource_info = self.get_resource_info(resource_def)
            except ModeNotSpecified:
                resource_def = copy.deepcopy(MAPPINGS['area_nomode'])
                resource_info = 'Please specify a mode for resource information Valid modes: %s'
                resource_info %= (','.join(self._data_manager.get_valid_modes(self.component)),)
            if flask.request.method == 'GET':
                if identifier is None:
                    return self.get_resource_data_root(resource_def, resource_info)
                else:
                    return self.get(identifier, resource_def, resource_info)
            # Only translate the data if this is not a RPC call
            if flask.request.method == 'POST' and self.api_req.content_type == 'application/json-rpc':
                translated_data = self.api_req.data
            else:
                translated_data = self.translate_data_for_datamanager(self.api_req.data, resource_def)
            if flask.request.method == 'PATCH':
                return self.patch(identifier, translated_data, resource_def, resource_info)
            elif flask.request.method == 'POST':
                return self.post(identifier, translated_data, resource_def, resource_info)
            elif flask.request.method == 'PUT':
                return self.put(identifier, translated_data, resource_def, resource_info)
        except ModeUnknown as err:
            msg = 'Invalid mode specified [%s].  Valid modes: %s'
            error = {
                'error': msg % (err.mode, ','.join(self._data_manager.get_valid_modes(self.component)),)
            }
            return (error, 400)
        except (ModeNotSpecified, NoModeSpecified):
            msg = 'Please specify a mode for resource information.  Valid modes: %s'
            error = {
                'error': msg % (','.join(self._data_manager.get_valid_modes(self.component)),)
            }
            return (error, 400)
        except UpdateIssue as err:
            return (err.issues, 422)
        except UnknownIdentifier:
            return (None, 404)

    def delete(self, identifier, *args, **kwargs):
        """ API Call to remove data """
        try:
            resource = self._data_manager.get_resource(self.component, identifier)
            resource.delete()
        except DependencyError as err:
            errors = []
            for section, identifier in err.dependencies:
                # TODO - Fix TBD if name is not present
                try:
                    resource = self._data_manager.get_resource(section, identifier)
                    name = resource.get(resource.name_field, 'TBD')
                    errors.append({
                        'name': name,
                        'uri': '%s/%s' % (flask.url_for('api_%s' % (section,)), identifier,)
                    })
                except InvalidSection:
                    errors.append({
                        'name': section,
                        'identifier': identifier
                    })
            return (errors, 412)
        else:
            headers = {
                'X-Status': 'Successfully deleted the object'
            }
            return (None, 202, {'headers': headers})

    def get(self, identifier, resource_def, resource_info, *args, **kwargs):
        """ API call to get data """
        try:
            resource = self._data_manager.get_resource(self.component, identifier)
            if resource_def.configuration:
                resource = self.translate_data_for_response(resource)
            return (resource, 200)
        except UnknownIdentifier:
            return (None, 404)

    def patch(self, identifier, data, resource_def, resource_info, *args, **kwargs):
        """ API call to update data """
        append = self.api_req.headers.get('X-Append', False)
        try:
            resource = resource_def(self._data_manager, identifier=identifier)
            resource.update(data, append=append)
            resource.save()
        except UnknownIdentifier:
            return (None, 404)
        else:
            headers = {
                'X-Status': 'Successfully updated the object'
            }
            return (None, 204, {'headers': headers})

    def post(self, identifier, data, resource_def, resource_info, *args, **kwargs):
        """ API call to create data """
        resource = resource_def(self._data_manager)
        if identifier is None:
            try:
                resource.update(data)
                resource.save()
                identifier = resource.identifier
            except SaveIssue as err:
                # TODO - lets handle with a real exception.  Most likely a dupe key that should be presented to the user
                return (str(err.args[0]), 400)
            uri = '%s/%s' % (flask.url_for('api_%s' % (self.component,)), identifier)
            headers = {
                'Location': resource.identifier,
                'X-Uri': uri,
                'X-Status': 'Successfully created the object'
            }
            converted = self.translate_data_for_response(resource)
            return (converted, 201, {'headers': headers})
        else:
            return (flask.request.method, 405)

    def put(self, identifier, data, resource_def, resource_info, *args, **kwargs):
        """ API call to replace an object """
        try:
            # Validate the resource exists before performing the replace
            resource = resource_def(self._data_manager, identifier=identifier)
            # Create an empty resource and pre-load the identifier prior to saving
            resource = resource_def(self._data_manager)
            resource.update(data)
            resource.identifier = identifier
            resource.save()
        except UnknownIdentifier:
            headers = {
                'X-Status': 'Object does not exist to update'
            }
            return (None, 404, {'headers': headers})
        else:
            headers = {
                'X-Status': 'Successfully replaced the object'
            }
            return (None, 204, {'headers': headers})
