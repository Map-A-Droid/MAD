import sys

from mapadroid.utils.logging import logger

# Most of the code is from RocketMap
# https://github.com/RocketMap/RocketMap
# Trying to import matplotlib, which is not compatible with all hardware.
# Matlplotlib is faster for big calculations.
try:
    from matplotlib.path import Path
except ImportError:
    # Pass as this is an optional requirement. We're going to check later if it
    # was properly imported and only use it if it's installed.
    pass


class GeofenceHelper:
    def __init__(self, include_geofence, exclude_geofence):
        self.geofenced_areas = []
        self.excluded_areas = []
        self.use_matplotlib = 'matplotlib' in sys.modules
        if include_geofence or exclude_geofence:
            self.geofenced_areas = self.parse_geofences_file(
                include_geofence, excluded=False)
            self.excluded_areas = self.parse_geofences_file(
                exclude_geofence, excluded=True)
            logger.debug2("Loaded {} geofenced and {} excluded areas.", len(
                self.geofenced_areas), len(self.excluded_areas))

    def get_polygon_from_fence(self):
        maxLat, minLat, maxLon, minLon = -90, 90, -180, 180
        if self.geofenced_areas:
            for va in self.geofenced_areas:
                for fence in va['polygon']:
                    maxLat = max(fence['lat'], maxLat)
                    minLat = min(fence['lat'], minLat)
                    maxLon = max(fence['lon'], maxLon)
                    minLon = min(fence['lon'], minLon)

        return minLat, minLon, maxLat, maxLon

    def is_coord_inside_include_geofence(self, coordinate):
        # logger.debug("Checking if coord {} is inside fences", str(coordinate))
        # Coordinate is not valid if in one excluded area.
        if self._is_excluded(coordinate):
            # logger.debug("Coord {} is inside EXCLUDED fences", str(coordinate))
            return False

        # Coordinate is geofenced if in one geofenced area.
        if self.geofenced_areas:
            for va in self.geofenced_areas:
                if self._in_area(coordinate, va):
                    # logger.debug("Coord {} is inside fences", str(coordinate))
                    return True
        else:
            # logger.debug("No fences present, adding the coord")
            return True
        # logger.debug("Coord {} is not inside fences", str(coordinate))
        return False

    def get_geofenced_coordinates(self, coordinates):

        # Import: We are working with n-tuples in some functions be carefull
        # and do not break compatibility
        logger.debug('Using matplotlib: {}.', self.use_matplotlib)
        logger.debug('Found {} coordinates to geofence.', len(coordinates))

        geofenced_coordinates = []
        for c in coordinates:
            # Coordinate is not valid if in one excluded area.
            if self._is_excluded(c):
                continue

            # Coordinate is geofenced if in one geofenced area.
            if self.geofenced_areas:
                for va in self.geofenced_areas:
                    if self._in_area(c, va):
                        geofenced_coordinates.append(c)
                        break
            else:
                geofenced_coordinates.append(c)

        logger.debug2("Geofenced to {} coordinates",
                      len(geofenced_coordinates))
        return geofenced_coordinates

    def is_enabled(self):
        return self.geofenced_areas or self.excluded_areas

    @staticmethod
    def parse_geofences_file(geo_resource, excluded):
        geofences = []
        # Read coordinates of excluded areas from file.
        if geo_resource:
            lines = geo_resource['fence_data']
            first_line = True
            for line in geo_resource['fence_data']:
                line = line.strip()
                if len(line) == 0:  # Empty line.
                    continue
                elif line.startswith("["):  # Name line.
                    name = line.replace("[", "").replace("]", "")
                    geofences.append({
                        'excluded': excluded,
                        'name': name,
                        'polygon': []
                    })
                    logger.debug('Found geofence: {}', name)
                    first_line = False
                else:  # Coordinate line.
                    if first_line:
                        # Geofence file with no name
                        geofences.append({
                            'excluded': excluded,
                            'name': 'unnamed',
                            'polygon': []
                        })
                        logger.debug('Found geofence with no name')
                        first_line = False
                    lat, lon = line.split(",")
                    LatLon = {'lat': float(lat), 'lon': float(lon)}
                    geofences[-1]['polygon'].append(LatLon)

        return geofences

    def _is_excluded(self, coordinate):
        for ea in self.excluded_areas:
            if self._in_area(coordinate, ea):
                return True

        return False

    def _in_area(self, coordinate, area):
        point = {'lat': coordinate[0], 'lon': coordinate[1]}
        polygon = area['polygon']
        if self.use_matplotlib:
            return self.is_point_in_polygon_matplotlib(point, polygon)
        else:
            return self.is_point_in_polygon_custom(point, polygon)

    @staticmethod
    def is_point_in_polygon_matplotlib(point, polygon):
        pointTuple = (point['lat'], point['lon'])
        polygonTupleList = []
        for c in polygon:
            coordinateTuple = (c['lat'], c['lon'])
            polygonTupleList.append(coordinateTuple)

        polygonTupleList.append(polygonTupleList[0])
        path = Path(polygonTupleList)
        return path.contains_point(pointTuple)

    @staticmethod
    def is_point_in_polygon_custom(point, polygon):
        # Initialize first coordinate as default.
        maxLat = polygon[0]['lat']
        minLat = polygon[0]['lat']
        maxLon = polygon[0]['lon']
        minLon = polygon[0]['lon']

        for coords in polygon:
            maxLat = max(coords['lat'], maxLat)
            minLat = min(coords['lat'], minLat)
            maxLon = max(coords['lon'], maxLon)
            minLon = min(coords['lon'], minLon)

        if ((point['lat'] > maxLat) or (point['lat'] < minLat) or
                (point['lon'] > maxLon) or (point['lon'] < minLon)):
            return False

        inside = False
        lat1, lon1 = polygon[0]['lat'], polygon[0]['lon']
        N = len(polygon)
        for n in range(1, N + 1):
            lat2, lon2 = polygon[n % N]['lat'], polygon[n % N]['lon']
            if (min(lon1, lon2) < point['lon'] <= max(lon1, lon2) and
                    point['lat'] <= max(lat1, lat2)):
                if lon1 != lon2:
                    latIntersection = (
                            (point['lon'] - lon1) *
                            (lat2 - lat1) / (lon2 - lon1) +
                            lat1)

                if lat1 == lat2 or point['lat'] <= latIntersection:
                    inside = not inside

            lat1, lon1 = lat2, lon2

        return inside

    def get_middle_from_fence(self):
        maxLat, minLat, maxLon, minLon = -90, 90, -180, 180
        if self.geofenced_areas:
            for va in self.geofenced_areas:
                for fence in va['polygon']:
                    maxLat = max(fence['lat'], maxLat)
                    minLat = min(fence['lat'], minLat)
                    maxLon = max(fence['lon'], maxLon)
                    minLon = min(fence['lon'], minLon)

        return minLat + ((maxLat - minLat) / 2), minLon + ((maxLon - minLon) / 2)
