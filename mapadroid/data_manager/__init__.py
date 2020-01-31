import collections
import copy
from typing import Optional, List, Dict
from . import modules
from .dm_exceptions import (
    ModeUnknown,
    ModeNotSpecified,
    InvalidSection,
    DataManagerException
)
from .modules.resource import Resource
from mapadroid.db.DbWrapper import DbWrapper


# This is still known as the data manager but its more of a Resource Factory.  Its sole purpose is to produce a
# single resource or a list of resources
class DataManager(object):
    def __init__(self, dbc: DbWrapper, instance_id: int):
        self.dbc = dbc
        self.instance_id = instance_id
        self.__paused_devices = []

    def clear_on_boot(self) -> None:
        # This function should handle any on-boot clearing.  It is not initiated by __init__ on the off-chance that
        # a third-party integration has triggered the data_manager
        # Clear any route calcs because that thread is not active
        if self.instance_id:
            clear_recalcs = {
                'recalc_status': 0,
                'instance_id': self.instance_id
            }
            self.dbc.autoexec_update('settings_routecalc', clear_recalcs)

    def get_resource(self, section: str, identifier: Optional[int] = None, **kwargs) -> Resource:
        if section == 'area':
            return modules.AreaFactory(self, identifier=identifier)
        try:
            return modules.MAPPINGS[section](self, identifier=identifier)
        except KeyError:
            raise InvalidSection()

    def get_resource_def(self, section: str, **kwargs) -> Resource:
        mode = kwargs.get('mode', None)
        if section == 'area':
            if mode is None:
                raise ModeNotSpecified(mode)
            try:
                resource_class = modules.AREA_MAPPINGS[mode]
            except KeyError:
                raise ModeUnknown(mode)
        else:
            resource_class = modules.MAPPINGS[section]
        return resource_class

    def get_root_resource(self, section: str, **kwargs) -> Dict[int, Resource]:
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

    def get_settings(self, section: str, **kwargs) -> Dict[str, str]:
        resource_class = self.get_resource_def(section, **kwargs)
        config = resource_class.configuration
        valid_config = {}
        valid_config['fields'] = config['fields']
        try:
            valid_config['settings'] = config['settings']
        except KeyError:
            pass
        return valid_config

    def search(self, section: str, **kwargs) -> Dict[int, Resource]:
        resource_def = kwargs.get('resource_def', None)
        mode = kwargs.get('mode', None)
        params = kwargs.get('params', {})
        if resource_def is None:
            try:
                resource_def = self.get_resource_def(section, mode=mode)
            except DataManagerException:
                resource_def = copy.deepcopy(modules.MAPPINGS['area_nomode'])
        resources = resource_def.search(self.dbc, resource_def, self.instance_id, **params)
        results = collections.OrderedDict()
        for identifier in resources:
            resource = self.get_resource(section, identifier=identifier)
            results[identifier] = resource
        return results

    def get_valid_modes(self, section: str) -> List[str]:
        valid_modes = []
        if section == 'area':
            valid_modes = sorted(modules.AREA_MAPPINGS.keys())
        return valid_modes

    def set_device_state(self, dev_name: str, active: int) -> None:
        if active == 1:
            try:
                self.__paused_devices.remove(dev_name)
            except ValueError:
                pass
        else:
            if dev_name not in self.__paused_devices:
                self.__paused_devices.append(dev_name)

    def is_device_active(self, dev_name: str) -> bool:
        return dev_name not in self.__paused_devices
