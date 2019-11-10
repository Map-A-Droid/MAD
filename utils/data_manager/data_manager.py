import collections
import json
import madmin.api
import re
import six

class DataManagerException(Exception):
    pass

class DependencyError(DataManagerException):
    def __init__(self, dependencies):
        self.dependencies = dependencies
        super(DependencyError, self).__init__(dependencies)

class InvalidMode(DataManagerException):
    def __init__(self, mode):
        self.mode = mode
        super(InvalidMode, self).__init__(mode)

class UnknownIdentifier(DataManagerException):
    pass

class DataManager(object):
    def __init__(self, logger, args, instance):
        self._logger = logger
        self.__args = args
        self.__instance = instance

    def delete_data(self, location, identifier=None):
        pass

    def get_api_attribute(self, location, attribute):
        return getattr(madmin.api.valid_modules[location], attribute)

    def get_data(self, location, identifier=None, **kwargs):
        pass

    def get_sorted_data(self, data, display, location, fetch_all):
        pass

    def has_any_dependencies(self, location, config_section, identifier):
        pass

    def __process_location(self, location, identifier=None):
        pass

    def __recursive_update(self, d, u, append=False, settings=False):
        for k, v in six.iteritems(u):
            dv = d.get(k, {})
            if append and isinstance(dv, list):
                d[k] = dv + v
            elif isinstance(v, collections.Mapping):
                d[k] = self.recursive_update(dv, v, append=append, settings=k.lower() == 'settings')
            else:
                if settings and v is None:
                    try:
                        del d[k]
                    except KeyError:
                        pass
                elif settings and type(v) is str and len(v) == 0:
                    try:
                        del d[k]
                    except KeyError:
                        pass
                else:
                    d[k] = v
        return d

    def save_config(self):
        pass

    def set_data(self, location, action, data, **kwargs):
        pass

    def __translate_location(self, location):
        return self.get_api_attribute(location, 'component')

    def __translate_section(self, location):
        return self.get_api_attribute(location, 'config_section')

    def update(self):
        pass
