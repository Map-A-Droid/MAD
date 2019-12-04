import collections
import json
import madmin.api
import re
import six

from utils.logging import logger

class DataManagerException(Exception):
    pass

class DataManagerDependencyError(DataManagerException):
    def __init__(self, dependencies):
        self.dependencies = dependencies
        super(DataManagerDependencyError, self).__init__(dependencies)

class DataManagerInvalidMode(DataManagerException):
    def __init__(self, mode):
        self.mode = mode
        super(DataManagerInvalidMode, self).__init__(mode)

class DataManagerInvalidModeUnknownIdentifier(DataManagerException):
    pass

class DataManager(object):
    def __init__(self, args):
        self.__raw = {}
        self.__location = args.mappings
        self.update()

    def delete_data(self, location, identifier=None, force=False):
        self.update()
        config_section = location
        try:
            removal_list = []
            (location, config_section, identifier) = self.__process_location(location, identifier=identifier)
            try:
                self.has_any_dependencies(location, config_section, identifier)
            except DataManagerDependencyError:
                if not force:
                    raise
            # If we are removing a walker, check to see if we can remove any walkerareas
            if config_section == 'walker':
                walker_config = self.get_data(location, identifier=identifier)
                for walkerarea_id in walker_config['setup']:
                    try:
                        self.delete_data('walkerarea', identifier=walkerarea_id)
                    except DataManagerDependencyError as err:
                        # This should fire for every occasion because its assigned to this walker.  Check to see if
                        # the walkerarea is only assigned to the walker.  If so, slate it for removal
                        # This is a for loop on the off-chance it has been added to the walker multiple times
                        valid = True
                        for failure in err.dependencies:
                            if failure['uri'] != identifier:
                                valid = False
                                break
                        if valid:
                            removal_list.append(('walkerarea', walkerarea_id))
            del self.__raw[config_section]['entries'][identifier]
            self.save_config()
            for section, comp_id in removal_list:
                self.delete_data(section, identifier=comp_id)
            return None
        except AttributeError:
            logger.debug('Invalid URI set in location, {}', location)
            return None
        except KeyError:
            logger.debug('Data for {},{} not found in configuration file', location, identifier)
            raise
        return True

    def generate_uri(self, location, *args):
        try:
            uri = '/'.join(['{}' for x in range(0, 2 + len(args))])
            location_args = [madmin.api.BASE_URI, self.translate_location(location), *args]
            return uri.format(*location_args)
        except KeyError:
            logger.warning('Invalid location for URI generation: {}', location)
            return None

    def get_api_attribute(self, location, attribute):
        return getattr(madmin.api.valid_modules[location], attribute)

    def get_data(self, location, identifier=None, **kwargs):
        self.update()
        config_section = location
        # Allow it to fetch all of the data by default.  If this is an API request, it will pass in 0 by default
        fetch_all = kwargs.get('fetch_all', 1)
        mode = kwargs.get('mode', None)
        try:
            (location, config_section, identifier) = self.__process_location(location, identifier=identifier)
            data = self.__raw[config_section]['entries']
            if mode and config_section == 'areas':
                valid={}
                for key, data in data.items():
                    if data['mode'] == mode:
                        valid[key] = data
                data = valid
        except AttributeError:
            logger.debug('Invalid URI set in location, {}', location)
            return None
        except KeyError:
            logger.debug('Data for {},{} not found in configuration file', location, identifier)
            raise DataManagerInvalidModeUnknownIdentifier()
        try:
            if identifier is not None:
                return data[str(identifier)]
        except KeyError:
            logger.debug('Data for {},{} not found in configuration file', location, identifier)
            raise DataManagerInvalidModeUnknownIdentifier()
        if identifier is None:
            disp_field = kwargs.get('display_field', self.get_api_attribute(location, 'default_sort'))
            try:
                data = self.get_sorted_data(data, disp_field, location, fetch_all)
            except:
                data = self.get_sorted_data(data, self.get_api_attribute(location, 'default_sort'), location, fetch_all)
        return data

    def get_sorted_data(self, data, display, location, fetch_all):
        ordered_data = collections.OrderedDict()
        if display and len(data) > 0:
            sort_elem = data[list(data.keys())[0]][display]
            if type(sort_elem) == str:
                sorted_keys = sorted(data, key=lambda x: (data[x][display].lower()))
            else:
                sorted_keys = sorted(data, key=lambda x: (data[x][display]))
        else:
            sorted_keys = list(data.keys())
        for key in sorted_keys:
            if fetch_all or display is None:
                ordered_data[key] = data[key]
            else:
                ordered_data[key] = data[key][display]
        return ordered_data

    def has_any_dependencies(self, location, config_section, identifier):
        if config_section == 'areas':
            # Check for any walkerareas that use the area
            dependency_failures = []
            walkerareas = self.get_data("walkerarea")
            if walkerareas is None:
                return
            for walkerarea_id, walkerarea in walkerareas.items():
                if walkerarea['walkerarea'] != identifier:
                    continue
                failure = {
                    'uri': walkerarea_id,
                    'name': walkerarea['walkertext'] if 'walkertext' in walkerarea else 'Non-Labeled Walker Area'
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
            devices = self.get_data("device")
            if devices is None:
                return
            for device_id, device in devices.items():
                if device['pool'] != identifier:
                    continue
                failure = {
                    'uri': device_id,
                    'name': device['origin']
                }
                dependency_failures.append(failure)
            if dependency_failures:
                raise DataManagerDependencyError(dependency_failures)
        elif config_section == 'monivlist':
            # Check for any areas that use the monivlist
            dependency_failures = []
            areas = self.get_data("area")
            if areas is None:
                return
            for area_id, area in areas.items():
                try:
                    if area['settings']['mon_ids_iv'] != identifier:
                        continue
                except KeyError:
                    continue
                failure = {
                    'uri': area_id,
                    'name': area['name']
                }
                dependency_failures.append(failure)
            if dependency_failures:
                raise DataManagerDependencyError(dependency_failures)
        elif config_section == 'walker':
            # Check for any devices that use the walker
            dependency_failures = []
            devices = self.get_data("device")
            if devices is None:
                return
            for device_id, device in devices.items():
                if device['walker'] != identifier:
                    continue
                failure = {
                    'uri': device_id,
                    'name': device['origin']
                }
                dependency_failures.append(failure)
            if dependency_failures:
                raise DataManagerDependencyError(dependency_failures)
        elif config_section == 'walkerarea':
            # Check for any walkers that use the walkerarea
            dependency_failures = []
            walkers = self.get_data("walker")
            if walkers is None:
                return
            for walker_id, walker in walkers.items():
                if identifier not in walker['setup']:
                    continue
                failure = {
                    'uri': walker_id,
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

    def set_data(self, location, action, data, **kwargs):
        self.update()
        append = kwargs.get('append', True)
        identifier = kwargs.get('identifier', None)
        (location, config_section, identifier) = self.__process_location(location, identifier=identifier)
        processed = False
        if identifier is None and action != 'post':
            raise UnknownIdentifier(location, identifier)
        if action in ['patch', 'put']:
            if identifier not in self.__raw[config_section]['entries']:
                raise KeyError
            if config_section == 'walker' and not append:
                try:
                    walkerareas_update = set(data['setup'])
                    walkerareas_original = set(self.__raw[config_section]['entries'][identifier]['setup'])
                    removed_walkerareas = set(walkerareas_original) - set(walkerareas_update)
                    if removed_walkerareas:
                        logger.debug('Change in walkerarea detected. {}', removed_walkerareas)
                        for walkerarea in removed_walkerareas:
                            try:
                                self.delete_data('walkerarea', identifier=walkerarea)
                            except DataManagerDependencyError as err:
                                if len(err.dependencies) == 1:
                                    self.delete_data('walkerarea', identifier=walkerarea, force=True)
                                pass
                except KeyError:
                    pass
        if action == 'patch':
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
            if "entries" not in self.__raw[config_section]:
                self.__raw[config_section]['entries'] = {}
            self.__raw[config_section]['entries'][index] = data
            self.__raw[config_section]['index'] = int(index) + 1
            self.save_config()
            return index
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
            logger.critical('Unable to load configuration, {}', err)
