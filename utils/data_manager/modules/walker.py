from .. import dm_exceptions
from . import resource
from .walkerarea import WalkerArea

class Walker(resource.Resource):
    table = 'settings_walker'
    primary_key = 'walker_id'
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
                    "description": "Order of areas",
                    "expected": list,
                    "uri": True,
                    "data_source": "walkerarea",
                    "uri_source": "api_walkerarea"
                }
            }
        }
    }

    def get_dependencies(self):
        sql = 'SELECT `device_id` FROM `settings_devices` WHERE `walker_id` = %s'
        dependencies = self._dbc.autofetch_column(sql, args=(self.identifier,))
        for ind, walkerarea_id in enumerate(dependencies[:]):
            dependencies[ind] = ('device', walkerarea_id)
        return dependencies

    def delete(self):
        # Get all walkerareas to determine if they need to be cleaned up
        sql = "SELECT `walkerarea_id` FROM `settings_walker_to_walkerarea` WHERE `walker_id` = %s"
        walkerareas = self._dbc.autofetch_column(sql, args=(self.identifier,))
        super().delete()
        # Walkerarea cleanup if they are no longer aligned to anything
        sql = "SELECT COUNT(*) FROM `settings_walker_to_walkerarea` WHERE `walkerarea_id` = %s"
        for walkerarea_id in walkerareas:
            in_use = self._dbc.autofetch_value(sql, args=(walkerarea_id,))
            if not in_use:
                walkerarea = WalkerArea(self._logger, self._dbc, self.instance_id, identifier=walkerarea_id)
                walkerarea.delete()

    def _load(self):
        super()._load()
        mon_query = "SELECT `walkerarea_id` FROM `settings_walker_to_walkerarea` WHERE `walker_id` = %s"
        mons = self._dbc.autofetch_column(mon_query, args=(self.identifier))
        self._data['fields']['setup'] = mons

    def save(self):
        core_data = {
            'walkername': self._data['fields']['walkername']
        }
        super().save(core_data)
        del_data = {
            'walker_id': self.identifier
        }
        self._dbc.autoexec_delete('settings_walker_to_walkerarea', del_data)
        for walkerarea_id in self._data['fields']['setup']:
            mon_data = {
                'walker_id': self.identifier,
                'walkerarea_id': walkerarea_id
            }
            self._dbc.autoexec_insert('settings_walker_to_walkerarea', mon_data)
        return self.identifier
