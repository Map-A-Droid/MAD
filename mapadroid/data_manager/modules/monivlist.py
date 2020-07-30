import mysql.connector
from typing import Optional, List, Tuple
from .resource import Resource
from mapadroid.utils.logging import get_logger, LoggerEnums


logger = get_logger(LoggerEnums.data_manager)


class MonIVList(Resource):
    table = 'settings_monivlist'
    name_field = 'monlist'
    primary_key = 'monlist_id'
    search_field = 'name'
    translations = {
        'monlist': 'name'
    }
    configuration = {
        "fields": {
            "monlist": {
                "settings": {
                    "type": "text",
                    "require": True,
                    "description": "Name of global Monlist",
                    'expected': str
                }
            },
            "mon_ids_iv": {
                "settings": {
                    "type": "text",
                    "require": True,
                    "empty": [],
                    "description": "Encounter these mon ids while walking (Default: Empty List)",
                    "expected": list
                }
            }
        }
    }

    def get_dependencies(self) -> List[Tuple[str, int]]:
        tables = ['settings_area_iv_mitm', 'settings_area_mon_mitm', 'settings_area_raids_mitm']
        sql = 'SELECT `area_id` FROM `%s` WHERE `monlist_id` = %%s'
        dependencies = []
        for table in tables:
            area_dependencies = self._dbc.autofetch_column(sql % (table,), args=(self.identifier,))
            for ind, area_id in enumerate(area_dependencies[:]):
                dependencies.append(('area', area_id))
        return dependencies

    def _load(self) -> None:
        super()._load()
        mon_query = "SELECT `mon_id` FROM `settings_monivlist_to_mon` WHERE `monlist_id` = %s ORDER BY `mon_order` ASC"
        mons = self._dbc.autofetch_column(mon_query, args=(self.identifier))
        self._data['fields']['mon_ids_iv'] = mons

    def save(self, force_insert: Optional[bool] = False, ignore_issues: Optional[List[str]] = []) -> int:
        self.presave_validation(ignore_issues=ignore_issues)
        core_data = {
            'monlist': self._data['fields']['monlist']
        }
        super().save(core_data, force_insert=force_insert, ignore_issues=ignore_issues)
        del_data = {
            'monlist_id': self.identifier
        }
        self._dbc.autoexec_delete('settings_monivlist_to_mon', del_data)
        for ind, mon in enumerate(self._data['fields']['mon_ids_iv']):
            mon_data = {
                'monlist_id': self.identifier,
                'mon_id': mon,
                'mon_order': ind
            }
            try:
                self._dbc.autoexec_insert('settings_monivlist_to_mon', mon_data)
            except mysql.connector.Error:
                logger.info('Duplicate pokemon {} detected in list {}', mon, self.identifier,)
        return self.identifier
