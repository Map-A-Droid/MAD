from typing import Optional, Dict, List, Tuple
from .resource import Resource
from mapadroid.db.DbWrapper import DbWrapper


class Area(Resource):
    table = 'settings_area'
    name_field = 'name'
    primary_key = 'area_id'
    search_field = 'name'
    translations = {
        'mon_ids_iv': 'monlist_id'
    }

    def get_dependencies(self) -> List[Tuple[str, int]]:
        sql = 'SELECT `walkerarea_id` FROM `settings_walkerarea` WHERE `area_id` = %s'
        dependencies = self._dbc.autofetch_column(sql, args=(self.identifier,))
        for ind, walkerarea_id in enumerate(dependencies[:]):
            dependencies[ind] = ('walkerarea', walkerarea_id)
        return dependencies

    def get_resource(self, backend: Optional[bool] = False) -> Resource:
        resource = super().get_resource(backend=backend)
        resource['mode'] = self.area_type
        return resource

    def _load(self) -> None:
        super()._load()
        mode_query = "SELECT * FROM `%s` WHERE `area_id` = %%s" % (self.area_table,)
        mode_data = self._dbc.autofetch_row(mode_query, args=(self.identifier))
        mode_data = self.translate_keys(mode_data, 'load')
        for field, db_value in mode_data.items():
            if field in self.configuration['fields']:
                self._data['fields'][field] = db_value
            elif 'settings' in self.configuration and field in self.configuration[
                 'settings'] and db_value is not None:
                self._data['settings'][field] = db_value
            else:
                continue
        # get route-calc status
        routecalc = self._data_manager.get_resource('routecalc', self._data['fields']['routecalc'])
        self.recalc_status = routecalc.recalc_status

    def save(self, force_insert: Optional[bool] = False, ignore_issues: Optional[List[str]] = []) -> int:
        has_identifier = True if self.identifier else False
        self.presave_validation(ignore_issues=ignore_issues)
        core_data = {
            'name': self._data['fields']['name'],
            'mode': self.area_type
        }
        try:
            super().save(core_data, force_insert=force_insert, ignore_issues=ignore_issues)
            try:
                save_data = {}
                if self._data['settings']:
                    save_data.update(dict(self._data['settings']))
            except KeyError:
                pass
            for field in self.configuration['fields']:
                if field in core_data:
                    continue
                if field not in self._data['fields']:
                    continue
                save_data[field] = self._data['fields'][field]
            if save_data:
                save_data['area_id'] = self.identifier
                if 'routecalc' not in save_data or len(str(save_data['routecalc'])) == 0:
                    routecalc = self._data_manager.get_resource('routecalc')
                    routecalc['routefile'] = []
                    routecalc.save()
                    save_data['routecalc'] = routecalc.identifier
                save_data = self.translate_keys(save_data, 'save')
                self._dbc.autoexec_insert(self.area_table, save_data, optype="ON DUPLICATE")
            return self.identifier
        except Exception as err:
            if not has_identifier and self.identifier:
                del_data = {
                    self.primary_key: self.identifier,
                    'instance_id': self.instance_id
                }
                self._dbc.autoexec_delete(self.table, del_data)
            raise err

    @classmethod
    def search(cls, dbc: DbWrapper, res_obj: Resource, instance_id: int, *args, **kwargs):
        where = ""
        mode = kwargs.get('mode', None)
        where = "WHERE `instance_id` = %s"
        sql_args = [instance_id]
        if mode:
            where += " AND `mode` = %s\n"
            sql_args.append(mode)
        sql = "SELECT `%s`\n" \
              "FROM `%s`\n" \
              "%s\n" \
              "ORDER BY `%s` ASC" % (res_obj.primary_key, res_obj.table, where, res_obj.search_field)
        return dbc.autofetch_column(sql, args=tuple(sql_args))

    def validate_custom(self) -> Dict[str, List[Tuple[str, str]]]:
        issues = {}
        try:
            if self._data['fields']['geofence_included'] == self._data['fields']['geofence_excluded']:
                issues = {
                    'invalid': [('geofence_excluded', 'Cannot be the same as geofence_included')]
                }
        except KeyError:
            pass
        try:
            if self._data['fields']['level'] and self._data['fields']['init']:
                issues = {
                    'invalid': [('init', 'Cannot have init and level set to True at the same time. '
                                         'For leveling up init must be set False.')]
                }
        except KeyError:
            pass
        return issues
