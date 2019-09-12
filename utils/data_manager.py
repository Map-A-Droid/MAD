import collections
import json
import madmin.api
import re
import six

class DataManagerException(Exception):
    pass

class UnknownIdentifier(DataManagerException):
    pass

class DataManager(object):
    def __init__(self, logger, args):
        self._logger = logger
        self.__raw = {}
        self.__location = args.mappings
        self.update()

    def delete_data(self, location, identifier=None):
        self.update()
        config_section = location
        try:
            (location, config_section, identifier) = self.__process_location(location, identifier=identifier)
            del self.__raw[config_section]['entries'][identifier]
        except AttributeError:
            self._logger.debug('Invalid URI set in location, {}', location)
            return None
        except KeyError:
            self._logger.debug('Data for {},{} not found in configuration file', location, identifier)
            self._logger.debug(self.__raw)
            return None
        self.save_config()
        return True

    def generate_uri(self, location, *args):
        try:
            uri = '/'.join(['{}' for x in range(0, 2+len(args))])
            location_args = [madmin.api.BASE_URI, self.translate_location(location), *args]
            return uri.format(*location_args)
        except KeyError:
            self._logger.warning('Invalid location for URI generation: {}', location)
            return None

    def get_api_attribute(self, location, attribute):
        return getattr(madmin.api.valid_modules[location], attribute)

    def get_data(self, location, identifier=None, **kwargs):
        self.update()
        config_section = location
        try:
            (location, config_section, identifier) = self.__process_location(location, identifier=identifier)
            data = self.__raw[config_section]['entries']
        except AttributeError:
            self._logger.debug('Invalid URI set in location, {}', location)
            return None
        except KeyError:
            self._logger.debug('Data for {},{} not found in configuration file', location, identifier)
            return None
        try:
            if identifier is not None:
                return data[str(identifier)]
        except KeyError:
            self._logger.debug('Identifier {} not found in {}', identifier, location)
            return None
        if identifier is None and kwargs.get('uri', True):
            converted_data = {}
            for key, val in data.items():
                converted_data[self.generate_uri(location, key)] = val
            data = converted_data
        return data

    def __process_location(self, location, identifier=None):
        if '/' in location:
            match = re.search(r'/{0,1}api/(\w+)(/(\d+)){0,1}', location)
            location = str(match.group(1))
            identifier = match.group(3)
        config_section = str(self.translate_section(location))
        return (location, config_section, identifier)

    def recursive_update(self, d, u, append=False, settings=False):
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
        with open(self.__location, 'w') as outfile:
            json.dump(self.__raw, outfile, indent=4, sort_keys=True)

    def set_data(self, data, location, action, **kwargs):
        self.update()
        append = kwargs.get('append', True)
        identifier = kwargs.get('identifier', None)
        (location, config_section, identifier) = self.__process_location(location, identifier=identifier)
        processed = False
        if identifier is None and action != 'post':
            raise UnknownIdentifier(location, identifier)
        if action == 'patch':
            if identifier not in self.__raw[config_section]['entries']:
                raise KeyError
            self.__raw[config_section]['entries'][identifier] = self.recursive_update(self.__raw[config_section]['entries'][identifier],
                                                                                      data,
                                                                                      append=append)
            self.save_config()
            return True
        elif action == 'post':
            index = str(self.__raw[config_section]['index'])
            uri_key = self.generate_uri(config_section, index)
            self.__raw[config_section]['entries'][index] = data
            self.__raw[config_section]['index'] = int(index) + 1
            self.save_config()
            return uri_key
        elif action == 'put':
            if identifier not in self.__raw[config_section]['entries']:
                raise KeyError
            self.__raw[config_section]['entries'][identifier] = data
            self.save_config()
            return True

    def translate_location(self, location):
        return self.get_api_attribute(location, 'component')

    def translate_section(self, location):
        return self.get_api_attribute(location, 'config_section')

    def update(self):
        try:
            with open(self.__location, 'rb') as fh:
                self.__raw = json.load(fh)
            self._logger.debug('Successfully updated the mappings')
        except Exception as err:
            self._logger.critical('Unable to load configuration, {}', err)
