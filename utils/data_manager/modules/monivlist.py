from .. import dm_exceptions
from . import resource

class MonIVList(resource.Resource):
    table = 'settings_monivlist'
    primary_key = 'monlist_id'
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
                    "description": "Encounter these mon ids while walking",
                    "expected": list
                }
            }
        }
    }

    def get_dependencies(self):
        tables = ['settings_area_iv_mitm', 'settings_area_mon_mitm', 'settings_area_raids_mitm']
        sql = 'SELECT `area_id` FROM `%s` WHERE `monlist_id` = %%s'
        dependencies = []
        for table in tables:
            area_dependencies = self._dbc.autofetch_column(sql % (table,), args=(self.identifier,))
            for ind, area_id in enumerate(area_dependencies[:]):
                dependencies.append(('area', area_id))
        return dependencies

    def _load(self):
        super()._load()
        mon_query = "SELECT `mon_id` FROM `settings_monivlist_to_mon` WHERE `monlist_id` = %s"
        mons = self._dbc.autofetch_column(mon_query, args=(self.identifier))
        self._data['fields']['mon_ids_iv'] = mons

    def save(self):
        core_data = {
            'monlist': self._data['fields']['monlist']
        }
        super().save(core_data)
        del_data = {
            'monlist_id': self.identifier
        }
        self._dbc.autoexec_delete('settings_monivlist_to_mon', del_data)
        for mon in self._data['fields']['mon_ids_iv']:
            mon_data = {
                'monlist_id': self.identifier,
                'mon_id': mon
            }
            self._dbc.autoexec_insert('settings_monivlist_to_mon', mon_data)
        return self.identifier
