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
from mapadroid.utils.logging import get_logger, LoggerEnums


logger = get_logger(LoggerEnums.data_manager)


# This is still known as the data manager but its more of a Resource Factory.  Its sole purpose is to produce a
# single resource or a list of resources
class DataManager(object):
    def __init__(self, dbc: DbWrapper, instance_id: int):
        self.dbc = dbc
        self.instance_id = instance_id
        self.__paused_devices: List[int] = []

    def clear_on_boot(self) -> None:
        # This function should handle any on-boot clearing.  It is not initiated by __init__ on the off-chance that
        # a third-party integration has triggered the data_manager
        # Clear any route calcs because that thread is not active
        if self.instance_id:
            clear_recalcs = {
                'recalc_status': 0,
            }
            where = {
                'instance_id': self.instance_id
            }
            self.dbc.autoexec_update('settings_routecalc', clear_recalcs, where_keyvals=where)

    def fix_routecalc_on_boot(self) -> None:
        rc_sql = "IFNULL(id.`routecalc`, IFNULL(iv.`routecalc`, IFNULL(mon.`routecalc`, " \
                 "IFNULL(ps.`routecalc`, ra.`routecalc`))))"
        sql = "SELECT a.`area_id`, a.`instance_id` AS 'ain', rc.`routecalc_id`, rc.`instance_id` AS 'rcin'\n"\
              "FROM (\n"\
              " SELECT sa.`area_id`, sa.`instance_id`, %s AS 'routecalc'\n"\
              " FROM `settings_area` sa\n"\
              " LEFT JOIN `settings_area_idle` id ON id.`area_id` = sa.`area_id`\n"\
              " LEFT JOIN `settings_area_iv_mitm` iv ON iv.`area_id` = sa.`area_id`\n"\
              " LEFT JOIN `settings_area_mon_mitm` mon ON mon.`area_id` = sa.`area_id`\n"\
              " LEFT JOIN `settings_area_pokestops` ps ON ps.`area_id` = sa.`area_id`\n"\
              " LEFT JOIN `settings_area_raids_mitm` ra ON ra.`area_id` = sa.`area_id`\n"\
              ") a\n"\
              "INNER JOIN `settings_routecalc` rc ON rc.`routecalc_id` = a.`routecalc`\n"\
              "WHERE a.`instance_id` != rc.`instance_id`" % (rc_sql,)
        bad_entries = self.dbc.autofetch_all(sql)
        if bad_entries:
            logger.info('Routecalcs with mis-matched IDs present. {}', bad_entries)
            for entry in bad_entries:
                update = {
                    'instance_id': entry['ain']
                }
                where = {
                    'routecalc_id': entry['routecalc_id']
                }
                self.dbc.autoexec_update('settings_routecalc', update, where_keyvals=where)

    def get_resource(self, section: str, identifier: Optional[int] = None, **kwargs) -> Resource:
        if section == 'area':
            return modules.area_factory(self, identifier=identifier)
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
        return copy.deepcopy(resource_class)

    def get_root_resource(self, section: str, **kwargs) -> Dict[int, Resource]:
        default_sort = kwargs.get('default_sort', None)
        backend = kwargs.get('backend', False)
        resource_class = None
        table = None
        primary_key = None
        if section == 'area':
            resource_class = modules.area_factory
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

    def set_device_state(self, device_id: int, active: int) -> None:
        if active == 1:
            try:
                self.__paused_devices.remove(device_id)
            except ValueError:
                pass
        else:
            if device_id not in self.__paused_devices:
                self.__paused_devices.append(device_id)

    def is_device_active(self, device_id: int) -> bool:
        return device_id not in self.__paused_devices
