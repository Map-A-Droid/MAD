from . import modules
from .dm_exceptions import *
import collections
from utils.logging import logger

# This is still known as the data manager but its more of a Resource Factory.  Its sole purpose is to produce a
# single resource or a list of resources
class DataManager(object):
    def __init__(self, dbc, instance_id):
        self.dbc = dbc
        self.instance_id = instance_id
        self.__paused_devices = []

    def get_resource(self, section, identifier=None, **kwargs):
        if section == 'area':
            return modules.AreaFactory(self, identifier=identifier)
        try:
            return modules.MAPPINGS[section](self, identifier=identifier)
        except KeyError:
            raise dm_exceptions.InvalidSection()

    def get_resource_def(self, section, **kwargs):
        mode = kwargs.get('mode', None)
        if section == 'area':
            if mode is None:
                raise dm_exceptions.ModeNotSpecified(mode)
            try:
                resource_class = modules.AREA_MAPPINGS[mode]
            except KeyError:
                raise dm_exceptions.ModeUnknown(mode)
        else:
            resource_class = modules.MAPPINGS[section]
        return resource_class

    def get_root_resource(self, section, **kwargs):
        fetch_all = kwargs.get('fetch_all', 1)
        mode = kwargs.get('mode', None)
        default_sort = kwargs.get('default_sort', None)
        backend = kwargs.get('backend', False)
        resource_class = None
        table = None
        primary_key = None
        if section == 'area':
            resource_class = modules.AreaFactory
            table = modules.Area.table
            primary_key = modules.Area.primary_key
            default_sort = 'name'
        else:
            resource_class = modules.MAPPINGS[section]
            table = resource_class.table
            primary_key = resource_class.primary_key
        sql = 'SELECT `%s` FROM `%s` WHERE `instance_id` = %%s'
        args = [primary_key, table]
        if default_sort is None and hasattr(resource_class, 'search_field'):
            default_sort = resource_class.search_field
        if default_sort:
            sql += ' ORDER BY `%s`'
            args.append(default_sort)
        identifiers = self.dbc.autofetch_column(sql % tuple(args), args=(self.instance_id,))
        data = collections.OrderedDict()
        for identifier in identifiers:
            elem = resource_class(self, identifier=identifier)
            if backend:
                elem = elem.get_resource()
            data[identifier] = elem
        return data

    def get_settings(self, section, **kwargs):
        resource_class = self.get_resource_def(section, **kwargs)
        config = resource_class.configuration
        valid_config = {}
        valid_config['fields'] = config['fields']
        try:
            valid_config['settings'] = config['settings']
        except KeyError:
            pass
        return valid_config

    def search(self, section, **kwargs):
        resource_def = kwargs.get('resource_def', None)
        resource_info = kwargs.get('resource_info', None)
        params = kwargs.get('params', {})
        if resource_def is None:
            try:
                resource_def = self.get_resource_def(section, mode=mode)
            except utils.data_manager.dm_exceptions.DataManagerException:
                resource_def = copy.deepcopy(utils.data_manager.modules.MAPPINGS['area_nomode'])
        resources = resource_def.search(self.dbc, resource_def, self.instance_id, **params)
        results = collections.OrderedDict()
        for identifier in resources:
            resource = self.get_resource(section, identifier=identifier)
            results[identifier] = resource
        return results

    def get_valid_modes(self, section):
        valid_modes = []
        if section == 'area':
            valid_modes = sorted(modules.AREA_MAPPINGS.keys())
        return valid_modes

    def set_device_state(self, dev_name, active):
        if active == 1:
            try:
                self.__paused_devices.remove(dev_name)
            except ValueError:
                pass
        else:
            if dev_name not in self.__paused_devices:
                self.__paused_devices.append(dev_name)

    def is_device_active(self, dev_name):
        return dev_name not in self.__paused_devices
