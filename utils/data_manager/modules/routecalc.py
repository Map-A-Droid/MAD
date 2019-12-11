from . import resource
from .. import dm_exceptions
import json
from route.routecalc.ClusteringHelper import ClusteringHelper
from utils.collections import Location
from route.routecalc.util import *
from utils.logging import logger

class RouteCalc(resource.Resource):
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

    def get_dependencies(self):
        tables = ['settings_area_idle',
                  'settings_area_iv_mitm',
                  'settings_area_mon_mitm',
                  'settings_area_pokestops',
                  'settings_area_raids_mitm'
        ]
        columns = ['geofence_included', 'geofence_excluded']
        sql = 'SELECT `area_id` FROM `%s` WHERE `routecalc` = %%s'
        dependencies = []
        for table in tables:
            table_sql = sql % (table,)
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
        self._data['fields']['routefile'] = json.loads(data['routefile'])

    def save(self, force_insert=False, ignore_issues=[]):
        self.presave_validation(ignore_issues=ignore_issues)
        core_data = self.get_resource()
        core_data['routefile'] = json.dumps(self._data['fields']['routefile'])
        super().save(core_data=core_data, force_insert=force_insert, ignore_issues=ignore_issues)

    # =====================================================
    # ============ Resource-Specific Functions ============
    # =====================================================

    def calculate_new_route(self, coords, max_radius, max_coords_within_radius, delete_old_route, calc_type,
                            useS2, S2level, num_procs=0, overwrite_calculation=False, in_memory=False):
        if overwrite_calculation:
            calc_type = 'quick'
        if delete_old_route and in_memory is False:
            logger.debug("Deleting routefile...")
            self._data['fields']['routefile'] = []
            self.save()
        new_route = self.getJsonRoute(coords, max_radius, max_coords_within_radius, in_memory, num_processes=num_procs,
                                      algorithm=calc_type, useS2=useS2, S2level=S2level)
        return new_route

    def getJsonRoute(self, coords, maxRadius, maxCoordsInRadius, in_memory, num_processes=1, algorithm='optimized',
                     useS2: bool = False, S2level: int=15):
        export_data = []
        if useS2: logger.debug("Using S2 method for calculation with S2 level: {}", S2level)
        if not in_memory and \
           (self._data['fields']['routefile'] is not None and len(self._data['fields']['routefile']) > 0):
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
        if len(coords) > 1 and maxRadius and maxCoordsInRadius:
            logger.info("Calculating...")
            newCoords = self.getLessCoords(coords, maxRadius, maxCoordsInRadius, useS2, S2level)
            lessCoordinates = np.zeros(shape=(len(newCoords), 2))
            for i in range(len(lessCoordinates)):
                lessCoordinates[i][0] = newCoords[i][0]
                lessCoordinates[i][1] = newCoords[i][1]
            logger.debug("Coords summed up: {}, that's just {} coords",
                         str(lessCoordinates), str(len(lessCoordinates)))
        logger.debug("Got {} coordinates", len(lessCoordinates))
        if len(lessCoordinates) < 3:
            logger.debug("less than 3 coordinates... not gonna take a shortest route on that")
            export_data = []
            for i in range(len(lessCoordinates)):
                export_data.append({'lat': lessCoordinates[i][0].item(),
                                    'lng': lessCoordinates[i][1].item()})
            return export_data
        logger.info("Calculating a short route through all those coords. Might take a while")
        from timeit import default_timer as timer
        start = timer()
        if algorithm == 'quick':
            from route.routecalc.calculate_route_quick import route_calc_impl
        else:
            from route.routecalc.calculate_route_optimized import route_calc_impl
        sol_best = route_calc_impl(lessCoordinates, num_processes)
        end = timer()
        logger.info("Calculated route in {} minutes", str((end - start) / 60))
        calc_coords = []
        for i in range(len(sol_best)):
            calc_coord = '%s,%s' % (str(lessCoordinates[int(sol_best[i])][0].item()),
                                    str(lessCoordinates[int(sol_best[i])][1].item()))
            calc_coords.append(calc_coord)
            export_data.append({'lat': lessCoordinates[int(sol_best[i])][0].item(),
                                'lng': lessCoordinates[int(sol_best[i])][1].item()})
        self._data['fields']['routefile'] = calc_coords
        self.save()
        return export_data

    def getLessCoords(self, npCoordinates, maxRadius, maxCountPerCircle, useS2: bool=False, S2level: int=15):
        coordinates = []
        for coord in npCoordinates:
            coordinates.append(
                (0, Location(coord[0].item(), coord[1].item()))
            )

        clustering_helper = ClusteringHelper(max_radius=maxRadius, max_count_per_circle=maxCountPerCircle,
                                             max_timedelta_seconds=0, useS2=useS2, S2level=S2level)
        clustered_events = clustering_helper.get_clustered(coordinates)
        coords_cleaned_up = []
        for event in clustered_events:
            coords_cleaned_up.append(event[1])
        return coords_cleaned_up