from typing import List, Optional, Tuple

from ..dm_exceptions import DataManagerException
from .resource import Resource
from .walkerarea import WalkerArea


class Walker(Resource):
    table = 'settings_walker'
    name_field = 'walkername'
    primary_key = 'walker_id'
    search_field = 'name'
    translations = {
        'walkername': 'name'
    }
    configuration = {
        "fields": {
            "walkername": {
                "settings": {
                    "type": "text",
                    "require": True,
                    "description": "Name of walker",
                    "expected": str
                }
            },
            "setup": {
                "settings": {
                    "type": "list",
                    "require": True,
                    "empty": [],
                    "description": "Order of areas  (Default: Empty List)",
                    "expected": list,
                    "uri": True,
                    "data_source": "walkerarea",
                    "uri_source": "api_walkerarea"
                }
            }
        }
    }

    def get_dependencies(self) -> List[Tuple[str, int]]:
        sql = 'SELECT `device_id` FROM `settings_device` WHERE `walker_id` = %s'
        dependencies = self._dbc.autofetch_column(sql, args=(self.identifier,))
        for ind, device_id in enumerate(dependencies[:]):
            dependencies[ind] = ('device', device_id)
        return dependencies

    def delete(self) -> None:
        # Get all walkerareas to determine if they need to be cleaned up
        sql = "SELECT `walkerarea_id` FROM `settings_walker_to_walkerarea` WHERE `walker_id` = %s"
        walkerareas = self._dbc.autofetch_column(sql, args=(self.identifier,))
        super().delete()
        # Walkerarea cleanup if they are no longer aligned to anything
        sql = "SELECT COUNT(*) FROM `settings_walker_to_walkerarea` WHERE `walkerarea_id` = %s"
        for walkerarea_id in walkerareas:
            in_use = self._dbc.autofetch_value(sql, args=(walkerarea_id,))
            if not in_use:
                walkerarea = WalkerArea(self._data_manager, identifier=walkerarea_id)
                walkerarea.delete()

    def _load(self) -> None:
        super()._load()
        mon_query = "SELECT `walkerarea_id`\n" \
                    "FROM `settings_walker_to_walkerarea`\n" \
                    "WHERE `walker_id` = %s ORDER BY `area_order` ASC"
        mons = self._dbc.autofetch_column(mon_query, args=(self.identifier))
        self._data['fields']['setup'] = mons

    def save(self, force_insert: Optional[bool] = False, ignore_issues: Optional[List[str]] = None) -> int:
        if ignore_issues is None:
            ignore_issues = []
        self.presave_validation(ignore_issues=ignore_issues)
        core_data = {
            'walkername': self._data['fields']['walkername']
        }
        super().save(core_data=core_data, force_insert=force_insert, ignore_issues=ignore_issues)
        # Get all current walkerareas
        sql = "SELECT `walkerarea_id` FROM `settings_walker_to_walkerarea` WHERE `walker_id` = %s"
        walkerareas = self._dbc.autofetch_column(sql, args=(self.identifier,))
        removed_walkerareas = set(walkerareas) - set(self._data['fields']['setup'])
        # Remove old walkerareas from the table
        del_data = {
            'walker_id': self.identifier
        }
        self._dbc.autoexec_delete('settings_walker_to_walkerarea', del_data)
        for ind, walkerarea_id in enumerate(self._data['fields']['setup']):
            walkerarea_data = {
                'walker_id': self.identifier,
                'walkerarea_id': walkerarea_id,
                'area_order': ind
            }
            self._dbc.autoexec_insert('settings_walker_to_walkerarea', walkerarea_data)
        for removed in removed_walkerareas:
            try:
                resource = self._data_manager.get_resource('walkerarea', identifier=removed)
                resource.delete()
            except DataManagerException:
                pass
        return self.identifier
