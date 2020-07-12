import json
from typing import Optional, Dict, List, Tuple
from .resource import Resource
from ..dm_exceptions import UnknownIdentifier
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.utils.logging import get_logger, LoggerEnums


logger = get_logger(LoggerEnums.data_manager)


class GeoFence(Resource):
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

    def get_dependencies(self) -> List[Tuple[str, int]]:
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
                except TypeError:
                    pass
        return dependencies

    def _load(self) -> None:
        query = "SELECT * FROM `%s` WHERE `%s` = %%s AND `instance_id` = %%s" % (self.table, self.primary_key)
        data = self._dbc.autofetch_row(query, args=(self.identifier, self.instance_id))
        if not data:
            raise UnknownIdentifier()
        data = self.translate_keys(data, 'load')
        self._data['fields']['name'] = data['name']
        self._data['fields']['fence_type'] = data['fence_type']
        self._data['fields']['fence_data'] = json.loads(data['fence_data'])

    def save(self, force_insert: Optional[bool] = False, ignore_issues: Optional[List[str]] = []) -> int:
        self.presave_validation(ignore_issues=ignore_issues)
        core_data = self.get_resource()
        core_data['fence_data'] = json.dumps(self._data['fields']['fence_data'])
        return super().save(core_data=core_data, force_insert=force_insert, ignore_issues=ignore_issues)

    def validate_custom(self) -> Dict[str, List[Tuple[str, str]]]:
        issues = {}
        try:
            GeofenceHelper(self, None)
        except Exception as err:
            issues = {
                'invalid': [('fence_data', 'Must be one coord set per line (float,float)')]
            }
            logger.error("Invalid geofence detected for {}: {}", self.identifier, err)
        return issues
