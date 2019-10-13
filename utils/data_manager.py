import collections
import json
import madmin.api
import re
import six


class DataManagerException(Exception):
    pass


class DataManagerDependencyError(Exception):
    def __init__(self, dependencies):
        self.dependencies = dependencies
        super(DataManagerDependencyError, self).__init__(dependencies)


class DataManagerInvalidMode(Exception):
    def __init__(self, mode):
        self.mode = mode
        super(DataManagerInvalidMode, self).__init__(mode)


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
            removal_list = []
            (location, config_section, identifier) = self.__process_location(location, identifier=identifier)
            try:
                self.has_any_dependencies(location, config_section, identifier)
            except Exception as e:
                print(e)
            # If we are removing a walker, check to see if we can remove any walkerareas
            if config_section == 'walker':
                uri = self.generate_uri(location, identifier)
                walker_config = self.get_data(location, identifier=identifier)
                for walkerarea_uri in walker_config['setup']:
                    try:
                        self.delete_data(walkerarea_uri)
                    except DataManagerDependencyError as err:
                        # This should fire for every occasion because its assigned to this walker.  Check to see if
                        # the walkerarea is only assigned to the walker.  If so, slate it for removal
                        # This is a for loop on the off-chance it has been added to the walker multiple times
                        valid = True
                        for failure in err.dependencies:
                            if failure['uri'] != uri:
                                valid = False
                                break
                        if valid:
                            removal_list.append(walkerarea_uri)
            del self.__raw[config_section]['entries'][identifier]
            self.save_config()
            for uri in removal_list:
                self.delete_data(uri)
            return None
        except AttributeError:
            self._logger.debug('Invalid URI set in location, {}', location)
            return None
        except KeyError:
            self._logger.debug('Data for {},{} not found in configuration file', location, identifier)
            self._logger.debug(self.__raw)
            return None
        return True

    def generate_uri(self, location, *args):
        try:
            uri = '/'.join(['{}' for x in range(0, 2 + len(args))])
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

    def has_any_dependencies(self, location, config_section, identifier):
        uri = self.generate_uri(location, identifier)
        if config_section == 'areas':
            # Check for any walkerareas that use the area
            dependency_failures = []

            if self.get_data("walkerarea") is None:
                return

            for walkerarea_uri, walkerarea in self.get_data('walkerarea').items():
                if walkerarea['walkerarea'] != uri:
                    continue
                failure = {
                    'uri': walkerarea_uri,
                    'name': walkerarea['walkertext']
                }
                dependency_failures.append(failure)
            if dependency_failures:
                raise DataManagerDependencyError(dependency_failures)
        elif config_section == 'auth':
            # Auth does not have dependencies for any objects
            pass
        elif config_section == 'devices':
            # Devices are not dependencies for any objects
            pass
        elif config_section == 'devicesettings':
            # Check for any devices that use the devicesetting
            dependency_failures = []

            if self.get_data("device") is None:
                return

            for device_uri, device in self.get_data('device').items():
                if device['pool'] != uri:
                    continue
                failure = {
                    'uri': device_uri,
                    'name': device['origin']
                }
                dependency_failures.append(failure)
            if dependency_failures:
                raise DataManagerDependencyError(dependency_failures)
        elif config_section == 'monivlist':
            # Check for any areas that use the monivlist
            dependency_failures = []

            if self.get_data("areas") is None:
                return

            for area_uri, area in self.get_data('areas').items():
                try:
                    if area['settings']['mon_ids_iv'] != uri:
                        continue
                except KeyError:
                    continue
                failure = {
                    'uri': area_uri,
                    'name': area['name']
                }
                dependency_failures.append(failure)
            if dependency_failures:
                raise DataManagerDependencyError(dependency_failures)
        elif config_section == 'walker':
            # Check for any devices that use the walker
            dependency_failures = []

            if self.get_data("device") is None:
                return

            for device_uri, device in self.get_data('device').items():
                if device['walker'] != uri:
                    continue
                failure = {
                    'uri': device_uri,
                    'name': device['origin']
                }
                dependency_failures.append(failure)
            if dependency_failures:
                raise DataManagerDependencyError(dependency_failures)
        elif config_section == 'walkerarea':
            # Check for any walkers that use the walkerarea
            dependency_failures = []

            if self.get_data("walker") is None:
                return

            for walker_uri, walker in self.get_data('walker').items():
                if uri not in walker['setup']:
                    continue
                failure = {
                    'uri': walker_uri,
                    'name': walker['walkername']
                }
                dependency_failures.append(failure)
            if dependency_failures:
                raise DataManagerDependencyError(dependency_failures)

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
            if config_section == 'areas':
                try:
                    mode = kwargs.get('mode', None)
                    self.get_api_attribute(location, 'configuration')[mode]
                    data['mode'] = mode
                except (AttributeError, KeyError):
                    raise DataManagerInvalidMode(mode)

            if "index" in self.__raw[config_section]:
                index = str(self.__raw[config_section]['index'])
            else:
                index = 0
                self.__raw[config_section] = {"index": index}

            uri_key = self.generate_uri(config_section, index)

            if "entries" not in self.__raw[config_section]:
                self.__raw[config_section]['entries'] = {}

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
        except Exception as err:
            self._logger.critical('Unable to load configuration, {}', err)
