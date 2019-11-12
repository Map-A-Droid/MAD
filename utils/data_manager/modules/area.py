from .. import dm_exceptions
from . import resource

class Area(resource.Resource):
    table = 'settings_area'
    name_field = 'name'
    primary_key = 'area_id'
    search_field = 'name'
    translations = {
        'mon_ids_iv': 'monlist_id'
    }

    def get_dependencies(self):
        sql = 'SELECT `walkerarea_id` FROM `settings_walkerarea` WHERE `area_id` = %s'
        dependencies = self._dbc.autofetch_column(sql, args=(self.identifier,))
        for ind, walkerarea_id in enumerate(dependencies[:]):
            dependencies[ind] = ('walkerarea', walkerarea_id)
        return dependencies

    def _load(self):
        super()._load()
        mode_query = "SELECT * FROM `%s` WHERE `area_id` = %%s" % (self.area_table,)
        mode_data = self._dbc.autofetch_row(mode_query, args=(self.identifier))
        mode_data = self.translate_keys(mode_data, 'load')
        for field, val in mode_data.items():
            if field in self.configuration['fields']:
                self._data['fields'][field] = val
            elif 'settings' in self.configuration and field in self.configuration['settings'] and val is not None:
                self._data['settings'][field] = val
            else:
                continue

    def save(self):
        core_data = {
            'name': self._data['fields']['name'],
            'mode': self.area_type
        }
        super().save(core_data)
        try:
            save_data = {}
            if self._data['settings']:
                save_data.update(dict(self._data['settings']))
        except KeyError as err:
            pass
        for field in self.configuration['fields']:
            if field in core_data:
                continue
            if field not in self._data['fields']:
                continue
            save_data[field] = self._data['fields'][field]
        if save_data:
            save_data['area_id'] = self.identifier
            save_data = self.translate_keys(save_data, 'save')
            res = self._dbc.autoexec_insert(self.area_table, save_data, optype="ON DUPLICATE")
        return self.identifier
