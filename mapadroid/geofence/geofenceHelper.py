import sys
from mapadroid.utils.logging import get_logger, LoggerEnums


logger = get_logger(LoggerEnums.system)

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
    def __init__(self, include_geofence, exclude_geofence, fence_name=None):
        self.geofenced_areas = []
        self.excluded_areas = []
        self.use_matplotlib = 'matplotlib' in sys.modules
        if include_geofence or exclude_geofence:
            self.geofenced_areas = self.parse_geofences_file(
                include_geofence, excluded=False, fence_fallback=fence_name)
            self.excluded_areas = self.parse_geofences_file(
                exclude_geofence, excluded=True, fence_fallback=fence_name)
            logger.debug2("Loaded {} geofenced and {} excluded areas.", len(self.geofenced_areas),
                          len(self.excluded_areas))

    def get_polygon_from_fence(self):
        max_lat, min_lat, max_lon, min_lon = -90, 90, -180, 180
        if self.geofenced_areas:
            for va in self.geofenced_areas:
                for fence in va['polygon']:
                    max_lat = max(fence['lat'], max_lat)
                    min_lat = min(fence['lat'], min_lat)
                    max_lon = max(fence['lon'], max_lon)
                    min_lon = min(fence['lon'], min_lon)

        return min_lat, min_lon, max_lat, max_lon

    def is_coord_inside_include_geofence(self, coordinate):
        # Coordinate is not valid if in one excluded area.
        if self._is_excluded(coordinate):
            return False

        # Coordinate is geofenced if in one geofenced area.
        if self.geofenced_areas:
            for va in self.geofenced_areas:
                if self._in_area(coordinate, va):
                    return True
        else:
            return True
        return False

    def get_geofenced_coordinates(self, coordinates):

        # Import: We are working with n-tuples in some functions be carefull
        # and do not break compatibility
        logger.debug('Using matplotlib: {}.', self.use_matplotlib)
        logger.debug2('Found {} coordinates to geofence.', len(coordinates))

        geofenced_coordinates = []
        for coord in coordinates:
            # Coordinate is not valid if in one excluded area.
            if self._is_excluded(coord):
                continue

            # Coordinate is geofenced if in one geofenced area.
            if self.geofenced_areas:
                for va in self.geofenced_areas:
                    if self._in_area(coord, va):
                        geofenced_coordinates.append(coord)
                        break
            else:
                geofenced_coordinates.append(coord)

        logger.debug2("Geofenced to {} coordinates", len(geofenced_coordinates))
        return geofenced_coordinates

    def is_enabled(self):
        return self.geofenced_areas or self.excluded_areas

    @staticmethod
    def parse_geofences_file(geo_resource, excluded, fence_fallback=None):
        geofences = []
        # Read coordinates of excluded areas from file.
        if geo_resource:
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
                    logger.debug2('Found geofence: {}', name)
                    first_line = False
                else:  # Coordinate line.
                    if first_line:
                        fencename = "unnamed"
                        if fence_fallback is not None:
                            fencename = fence_fallback
                        # Geofence file with no name
                        geofences.append({
                            'excluded': excluded,
                            'name': fencename,
                            'polygon': []
                        })
                        logger.debug2('Found geofence with no name')
                        first_line = False
                    lat, lon = line.split(",")
                    coord = {'lat': float(lat), 'lon': float(lon)}
                    geofences[-1]['polygon'].append(coord)

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
        point_tuple = (point['lat'], point['lon'])
        polygons = []
        for coord in polygon:
            coord_tuple = (coord['lat'], coord['lon'])
            polygons.append(coord_tuple)

        polygons.append(polygons[0])
        path = Path(polygons)
        return path.contains_point(point_tuple)

    @staticmethod
    def is_point_in_polygon_custom(point, polygon):
        # Initialize first coordinate as default.
        max_lat = polygon[0]['lat']
        min_lat = polygon[0]['lat']
        max_lon = polygon[0]['lon']
        min_lon = polygon[0]['lon']

        for coords in polygon:
            max_lat = max(coords['lat'], max_lat)
            min_lat = min(coords['lat'], min_lat)
            max_lon = max(coords['lon'], max_lon)
            min_lon = min(coords['lon'], min_lon)

        if ((point['lat'] > max_lat) or (point['lat'] < min_lat) or
                (point['lon'] > max_lon) or (point['lon'] < min_lon)):
            return False

        inside = False
        lat1, lon1 = polygon[0]['lat'], polygon[0]['lon']
        poly_sides = len(polygon)
        for poly_point in range(1, poly_sides + 1):
            lat2, lon2 = polygon[poly_point % poly_sides]['lat'], polygon[poly_point % poly_sides]['lon']
            if (min(lon1, lon2) < point['lon'] <= max(lon1, lon2) and
                    point['lat'] <= max(lat1, lat2)):
                if lon1 != lon2:
                    lat_intersection = ((point['lon'] - lon1) * (lat2 - lat1) / (lon2 - lon1) + lat1)

                if lat1 == lat2 or point['lat'] <= lat_intersection:
                    inside = not inside

            lat1, lon1 = lat2, lon2

        return inside

    def get_middle_from_fence(self):
        max_lat, min_lat, max_lon, min_lon = -90, 90, -180, 180
        if self.geofenced_areas:
            for va in self.geofenced_areas:
                for fence in va['polygon']:
                    max_lat = max(fence['lat'], max_lat)
                    min_lat = min(fence['lat'], min_lat)
                    max_lon = max(fence['lon'], max_lon)
                    min_lon = min(fence['lon'], min_lon)

        return min_lat + ((max_lat - min_lat) / 2), min_lon + ((max_lon - min_lon) / 2)
