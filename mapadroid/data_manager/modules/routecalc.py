import json
import numpy as np
from typing import Optional, Dict, List, Tuple
from .resource import Resource
from ..dm_exceptions import UnknownIdentifier
from mapadroid.route.routecalc.ClusteringHelper import ClusteringHelper
from mapadroid.utils.collections import Location
from mapadroid.utils.logging import get_logger, LoggerEnums


logger = get_logger(LoggerEnums.data_manager)


class RouteCalc(Resource):
    table = 'settings_routecalc'
    primary_key = 'routecalc_id'
    configuration = {
        "fields": {
            "routefile": {
                "settings": {
                    "type": "textarea",
                    "require": True,
                    "empty": [],
                    "description": "Route to walk / teleport  (Default: Empty List)",
                    "expected": list
                }
            }
        }
    }

    def _default_load(self) -> None:
        self.recalc_status = False

    def get_dependencies(self) -> None:
        tables = ['settings_area_idle',
                  'settings_area_iv_mitm',
                  'settings_area_mon_mitm',
                  'settings_area_pokestops',
                  'settings_area_raids_mitm'
                  ]
        sql = 'SELECT `area_id` FROM `%s` WHERE `routecalc` = %%s'
        dependencies = []
        for table in tables:
            table_sql = sql % (table,)
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
        self._data['fields']['routefile'] = json.loads(data['routefile'])
        self.recalc_status = data['recalc_status']

    def save(self, force_insert: Optional[bool] = False, ignore_issues: Optional[List[str]] = [],
             update_time: bool = False) -> int:
        self.presave_validation(ignore_issues=ignore_issues)
        literals = []
        core_data = self.get_resource()
        core_data['routefile'] = json.dumps(self._data['fields']['routefile'])
        core_data['recalc_status'] = self.recalc_status
        if update_time:
            core_data['last_updated'] = 'NOW()'
            literals.append('last_updated')
        return super().save(core_data=core_data, force_insert=force_insert, ignore_issues=ignore_issues,
                            literals=literals)

    def validate_custom(self) -> Dict[str, List[Tuple[str, str]]]:
        issues = {}
        invalid_data = []
        for line, row in enumerate(self['routefile']):
            row_split = row.split(',')
            if len(row) == 0:
                continue
            if len(row_split) != 2:
                if not invalid_data:
                    issues = {
                        'invalid': [('routefile', 'Must be one coord set per line (float,float)')]
                    }
                invalid_data.append('Line %s does not contain two values' % (line,))
                continue
            for val in row_split:
                try:
                    float(val)
                except (TypeError, ValueError):
                    if not invalid_data:
                        issues = {
                            'invalid': [('routefile', 'Must be one coord set per line (float,float)')]
                        }
                    invalid_data.append('Line %s [%s] is not a float / decimal' % (line, val,))
        if invalid_data:
            logger.error("Invalid routecalc detected for {}: {}", self.identifier, invalid_data)
        return issues

    # =====================================================
    # ============ Resource-Specific Functions ============
    # =====================================================

    def calculate_new_route(self, coords: List[Tuple[str, str]], max_radius: int, max_coords_within_radius: int,
                            delete_old_route: bool, calc_type: str, useS2: bool, S2level: int, num_procs: int = 0,
                            overwrite_calculation: bool = False, in_memory: bool = False, route_name: str = 'Unknown'
                            ) -> List[Dict[str, float]]:
        if overwrite_calculation:
            calc_type = 'route'
        self.set_recalc_status(True)
        if in_memory is False:
            if delete_old_route:
                logger.debug("Deleting routefile...")
                self._data['fields']['routefile'] = []
                self.save()
        new_route = self.getJsonRoute(coords, max_radius, max_coords_within_radius, in_memory,
                                      num_processes=num_procs,
                                      algorithm=calc_type, useS2=useS2, S2level=S2level,
                                      route_name=route_name)
        self.set_recalc_status(False)
        return new_route

    def getJsonRoute(self, coords: List[Tuple[str, str]], max_radius: int, max_coords_within_radius: int,
                     in_memory: bool, num_processes: int = 1, algorithm: str = 'route', useS2: bool = False,
                     S2level: int = 15, route_name: str = 'Unknown') -> List[Dict[str, float]]:
        export_data = []
        if useS2:
            logger.debug("Using S2 method for calculation with S2 level: {}", S2level)
        if not in_memory and \
                (self._data['fields']['routefile'] is not None and len(
                    self._data['fields']['routefile']) > 0):
            logger.debug('Using routefile from DB')
            for line in self._data['fields']['routefile']:
                # skip empty lines
                if not line.strip():
                    continue
                lineSplit = line.split(',')
                export_data.append({'lat': float(lineSplit[0].strip()),
                                    'lng': float(lineSplit[1].strip())})
            return export_data

        lessCoordinates = coords
        if len(coords) > 0 and max_radius and max_coords_within_radius:
            logger.info("Calculating route for {}", route_name)
            newCoords = self.getLessCoords(coords, max_radius, max_coords_within_radius, useS2, S2level)
            lessCoordinates = np.zeros(shape=(len(newCoords), 2))
            for i in range(len(lessCoordinates)):
                lessCoordinates[i][0] = newCoords[i][0]
                lessCoordinates[i][1] = newCoords[i][1]
            logger.debug("Coords summed up: {}, that's just {} coords", lessCoordinates, len(lessCoordinates))
        logger.debug("Got {} coordinates", len(lessCoordinates))
        if len(lessCoordinates) < 3:
            logger.debug("less than 3 coordinates... not gonna take a shortest route on that")
            export_data = []
            for i in range(len(lessCoordinates)):
                export_data.append({'lat': lessCoordinates[i][0].item(),
                                    'lng': lessCoordinates[i][1].item()})
        else:
            logger.info("Calculating a short route through all those coords. Might take a while")
            from timeit import default_timer as timer
            start = timer()
            from mapadroid.route.routecalc.calculate_route_all import route_calc_all
            sol_best = route_calc_all(lessCoordinates, route_name, num_processes, algorithm)

            end = timer()

            calc_dur = (end - start) / 60
            time_unit = 'minutes'
            if calc_dur < 1:
                calc_dur = int(calc_dur * 60)
                time_unit = 'seconds'

            logger.info("Calculated route for {} in {} {}", route_name, calc_dur, time_unit)

            for i in range(len(sol_best)):
                export_data.append({'lat': lessCoordinates[int(sol_best[i])][0].item(),
                                    'lng': lessCoordinates[int(sol_best[i])][1].item()})
        if not in_memory:
            calc_coords = []
            for coord in export_data:
                calc_coord = '%s,%s' % (coord['lat'], coord['lng'])
                calc_coords.append(calc_coord)
            # Only save if we aren't calculating in memory
            self._data['fields']['routefile'] = calc_coords
            self.save(update_time=True)
        return export_data

    def getLessCoords(self, npCoordinates: List[Tuple[str, str]], max_radius: int, max_coords_within_radius: int,
                      useS2: bool = False, S2level: int = 15):
        coordinates = []
        for coord in npCoordinates:
            coordinates.append(
                (0, Location(coord[0].item(), coord[1].item()))
            )

        clustering_helper = ClusteringHelper(max_radius=max_radius, max_count_per_circle=max_coords_within_radius,
                                             max_timedelta_seconds=0, useS2=useS2, S2level=S2level)
        clustered_events = clustering_helper.get_clustered(coordinates)
        coords_cleaned_up = []
        for event in clustered_events:
            coords_cleaned_up.append(event[1])
        return coords_cleaned_up

    def set_recalc_status(self, status: int) -> None:
        data = {
            'recalc_status': int(status)
        }
        where = {
            self.primary_key: self.identifier
        }
        self._dbc.autoexec_update(self.table, data, where_keyvals=where)
