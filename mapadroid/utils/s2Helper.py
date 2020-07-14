import math
import multiprocessing
from typing import List
import gpxdata
import s2sphere
# from utils.collections import Location
# from utils.geo import get_middle_of_coord_list, get_distance_of_two_points_in_meters
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.utils.collections import Location
from mapadroid.utils.geo import (
    get_distance_of_two_points_in_meters,
    get_middle_of_coord_list
)
from mapadroid.utils.logging import get_logger, LoggerEnums


logger = get_logger(LoggerEnums.utils)


class S2Helper:
    @staticmethod
    def lat_lng_to_cell_id(lat, lng, level=10):
        region_cover = s2sphere.RegionCoverer()
        region_cover.min_level = level
        region_cover.max_level = level
        region_cover.max_cells = 1
        p1 = s2sphere.LatLng.from_degrees(lat, lng)
        p2 = s2sphere.LatLng.from_degrees(lat, lng)
        covering = region_cover.get_covering(
            s2sphere.LatLngRect.from_point_pair(p1, p2))
        # we will only get our desired cell ;)
        return covering[0].id()

    # RM stores lat, long as well...
    # returns tuple  <lat, lng>
    @staticmethod
    def middle_of_cell(cell_id):
        cell = s2sphere.CellId(cell_id)
        lat_lng = cell.to_lat_lng()
        return lat_lng.lat().degrees, lat_lng.lng().degrees

    @staticmethod
    def coords_of_cell(cell_id):
        cell = s2sphere.Cell(s2sphere.CellId(int(cell_id)))
        coords = []
        for value in range(0, 4):
            vertex = s2sphere.LatLng.from_point(cell.get_vertex(value))
            coords.append([vertex.lat().degrees, vertex.lng().degrees])
        return coords

    @staticmethod
    def calc_s2_cells(north, south, west, east, cell_size=16):
        centers_in_area = []
        region = s2sphere.RegionCoverer()
        region.min_level = cell_size
        region.max_level = cell_size
        p1 = s2sphere.LatLng.from_degrees(north, west)
        p2 = s2sphere.LatLng.from_degrees(south, east)
        cell_ids = region.get_covering(
            s2sphere.LatLngRect.from_point_pair(p1, p2))
        logger.debug('Detecting {} L{} Cells in Area', len(cell_ids), cell_size)
        for cell_id in cell_ids:
            split_cell_id = str(cell_id).split(' ')
            position = S2Helper.get_position_from_cell(
                int(split_cell_id[1], 16))
            centers_in_area.append([position[0], position[1]])
            # calc_route_data.append(str(position[0]) + ', ' + str(position[1]))

        return centers_in_area

    @staticmethod
    def get_position_from_cell(cell_id):
        cell = s2sphere.CellId(id_=int(cell_id)).to_lat_lng()
        return s2sphere.math.degrees(cell.lat().radians), s2sphere.math.degrees(cell.lng().radians), 0

    @staticmethod
    def get_s2_cells_from_fence(geofence, cell_size=16):
        _geofence = geofence
        logger.warning("Calculating corners of fences")
        south, east, north, west = _geofence.get_polygon_from_fence()
        calc_route_data = []
        region = s2sphere.RegionCoverer()
        region.min_level = cell_size
        region.max_level = cell_size
        p1 = s2sphere.LatLng.from_degrees(north, west)
        p2 = s2sphere.LatLng.from_degrees(south, east)
        logger.warning("Calculating coverage of region")
        cell_ids = region.get_covering(
            s2sphere.LatLngRect.from_point_pair(p1, p2))

        logger.warning("Iterating cell_ids")
        for cell_id in cell_ids:
            split_cell_id = str(cell_id).split(' ')
            position = S2Helper.middle_of_cell(int(split_cell_id[1], 16))
            calc_route_data.append([position[0], position[1]])
        logger.debug('Detecting {} L{} Cells in Area', len(calc_route_data), cell_size)

        return calc_route_data

    @staticmethod
    def get_cellid_from_latlng(lat, lng, level=20):
        ll = s2sphere.LatLng.from_degrees(lat, lng)
        cell = s2sphere.CellId().from_lat_lng(ll)
        return cell.parent(level).to_token()

    @staticmethod
    def _generate_star_locs(center, distance, ring):
        results = []
        for i in range(0, 6):
            # Star_locs will contain the locations of the 6 vertices of
            # the current ring (90,150,210,270,330 and 30 degrees from
            # origin) to form a star
            star_loc = S2Helper.get_new_coords(center, distance * ring,
                                               90 + 60 * i)
            for index in range(0, ring):
                # Then from each point on the star, create locations
                # towards the next point of star along the edge of the
                # current ring
                loc = S2Helper.get_new_coords(star_loc, distance * index, 210 + 60 * i)
                results.append(loc)
        return results

    # the following stuff is drafts for further consideration
    @staticmethod
    def _generate_locations(distance: float, geofence_helper: GeofenceHelper):
        south, east, north, west = geofence_helper.get_polygon_from_fence()

        corners = [
            Location(south, east),
            Location(south, west),
            Location(north, east),
            Location(north, west)
        ]
        # get the center
        center = get_middle_of_coord_list(corners)

        # get the farthest to the center...
        farthest_dist = 0
        for corner in corners:
            dist_temp = get_distance_of_two_points_in_meters(
                center.lat, center.lng, corner.lat, corner.lng)
            if dist_temp > farthest_dist:
                farthest_dist = dist_temp

        # calculate step_limit, round up to reduce risk of losing stuff
        step_limit = math.ceil(farthest_dist / distance)

        # This will loop thorugh all the rings in the hex from the centre
        # moving outwards
        logger.info("Calculating positions for init scan")
        num_cores = multiprocessing.cpu_count()
        with multiprocessing.Pool(processes=num_cores) as pool:
            temp = [pool.apply(S2Helper._generate_star_locs, args=(
                center, distance, i)) for i in range(1, step_limit)]

        results = [item for sublist in temp for item in sublist]
        results.append(Location(center.lat, center.lng))

        # for ring in range(1, step_limit):
        #     for i in range(0, 6):
        #         # Star_locs will contain the locations of the 6 vertices of
        #         # the current ring (90,150,210,270,330 and 30 degrees from
        #         # origin) to form a star
        #         star_loc = S2Helper.get_new_coords(center, distance * ring,
        #                                            90 + 60 * i)
        #         for j in range(0, ring):
        #             # Then from each point on the star, create locations
        #             # towards the next point of star along the edge of the
        #             # current ring
        #             loc = S2Helper.get_new_coords(star_loc, distance * j, 210 + 60 * i)
        #             results.append(loc)

        logger.info("Filtering positions for init scan")
        # Geofence results.
        if geofence_helper is not None and geofence_helper.is_enabled():
            results = geofence_helper.get_geofenced_coordinates(results)
            if not results:
                logger.error('No cells regarded as valid for desired scan area. Check your provided geofences. '
                             'Aborting.')
            else:
                logger.info("Ordering location")
                results = S2Helper.order_location_list_rows(results)
        return results

    @staticmethod
    def get_most_north(location_list):
        if location_list is None or len(location_list) == 0:
            return None
        most_north_and_east = location_list[0]
        for location in location_list:
            if location.lat > most_north_and_east.lat + 1e-5:
                most_north_and_east = location
        return most_north_and_east

    @staticmethod
    def order_location_list_rows(location_list: List[Location]):
        if location_list is None or len(location_list) == 0:
            return []

        new_list = []
        flip = False
        while len(location_list) > 0:
            next_row = S2Helper.get_most_northern_row(location_list)
            next_row = S2Helper.sort_row_from_west(next_row)
            if flip:
                next_row.reverse()
                flip = False
            else:
                flip = True
            for loc in next_row:
                new_list.append(loc)
            location_list = S2Helper.delete_row_from_list(
                location_list, next_row)
        return new_list

    @staticmethod
    def get_most_northern_row(location_list: List[Location]):
        if location_list is None or len(location_list) == 0:
            return []

        most_north = S2Helper.get_most_north(location_list)
        row = []
        for location in location_list:
            if most_north.lat - 1e-4 <= location.lat <= most_north.lat + 1e-4:
                row.append(location)

        return row

    @staticmethod
    def delete_row_from_list(location_list, row):
        if row is None or len(row) == 0:
            return location_list
        elif location_list is None or len(location_list) == 0:
            return []

        for loc in row:
            location_list.remove(loc)
        return location_list

    @staticmethod
    def sort_row_from_west(row):
        if row is None or len(row) == 0:
            return []
        return sorted(row, key=lambda x: x.lng)

    @staticmethod
    def get_most_west(location_list):
        if location_list is None or len(location_list) == 0:
            return []

        most_west = location_list[0]
        for location in location_list:
            if location.lng < most_west.lng:
                most_west = location

        return most_west

    @staticmethod
    # Returns destination coords given origin coords, distance (Kms) and bearing.
    def get_new_coords(init_loc, distance, bearing):
        """
        Given an initial lat/lng, a distance(in kms), and a bearing (degrees),
        this will calculate the resulting lat/lng coordinates.
        """
        # TODO: check for implementation with gpxdata
        start = gpxdata.TrackPoint(init_loc.lat, init_loc.lng)
        destination = start + gpxdata.CourseDistance(bearing, distance)

        return Location(destination.lat, destination.lon)

    @staticmethod
    # Returns a set of S2 cells within circle around position
    def get_S2cells_from_circle(lat, lng, radius, level=15):
        EARTH = 6371000
        region = s2sphere.Cap.from_axis_angle(s2sphere.LatLng.from_degrees(lat, lng).to_point(),
                                              s2sphere.Angle.from_degrees(360 * radius / (2 * math.pi * EARTH)))
        coverer = s2sphere.RegionCoverer()
        coverer.min_level = level
        coverer.max_level = level
        cells = coverer.get_covering(region)
        return cells
