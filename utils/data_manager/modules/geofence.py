from . import resource
from .. import dm_exceptions
import json
from geofence.geofenceHelper import GeofenceHelper

class GeoFence(resource.Resource):
    table = 'settings_geofence'
    name_field = 'name'
    primary_key = 'geofence_id'
    search_field = 'name'
    configuration = {
        "fields": {
            "name": {
                "settings": {
                    "type": "text",
                    "require": True,
                    "description": "Name of the geofence",
                    "expected": str
                }
            },
            "fence_type": {
                "settings": {
                    "type": "option",
                    "require": True,
                    "values": ['polygon'],
                    "description": "Type of the geofence",
                    "expected": str
                }
            },
            "fence_data": {
                "settings": {
                    "type": "textarea",
                    "require": True,
                    "empty": [],
                    "description": "Data for the geofence (Default: Empty List)",
                    "expected": list
                }
            }
        }
    }

    def get_dependencies(self):
        tables = ['settings_area_idle',
                  'settings_area_iv_mitm',
                  'settings_area_mon_mitm',
                  'settings_area_pokestops',
                  'settings_area_raids_mitm'
        ]
        columns = ['geofence_included', 'geofence_excluded']
        sql = 'SELECT `area_id` FROM `%s` WHERE `%s` = %%s'
        dependencies = []
        for table in tables:
            for column in columns:
                if column == 'geofence_excluded' and table == 'settings_area_idle':
                    continue
                table_sql = sql % (table, column,)
                try:
                    area_dependencies = self._dbc.autofetch_column(table_sql, args=(self.identifier))
                    for ind, area_id in enumerate(area_dependencies[:]):
                        dependencies.append(('area', area_id))
                except:
                    pass
        return dependencies

    def _load(self):
        query = "SELECT * FROM `%s` WHERE `%s` = %%s AND `instance_id` = %%s" % (self.table, self.primary_key)
        data = self._dbc.autofetch_row(query, args=(self.identifier, self.instance_id))
        if not data:
            raise dm_exceptions.UnknownIdentifier()
        data = self.translate_keys(data, 'load')
        self._data['fields']['name'] = data['name']
        self._data['fields']['fence_type'] = data['fence_type']
        self._data['fields']['fence_data'] = json.loads(data['fence_data'])

    def save(self, force_insert=False, ignore_issues=[]):
        self.presave_validation(ignore_issues=ignore_issues)
        core_data = self.get_resource()
        core_data['fence_data'] = json.dumps(self._data['fields']['fence_data'])
        super().save(core_data=core_data, force_insert=force_insert, ignore_issues=ignore_issues)

    def presave_validation(self, ignore_issues=[]):
        issues = {}
        try:
            geofence_helper = GeofenceHelper(self, None)
        except Exception as err:
            issues = {
                'invalid': [('fence_data', 'Must be one coord set per line (float,float)')]
            }
        super().presave_validation(ignore_issues=ignore_issues, issues=issues)