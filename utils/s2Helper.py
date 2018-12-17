import logging

import s2sphere

log = logging.getLogger(__name__)


class S2Helper:
    @staticmethod
    def lat_lng_to_cell_id(lat, lng, level=10):
        region_cover = s2sphere.RegionCoverer()
        region_cover.min_level = level
        region_cover.max_level = level
        region_cover.max_cells = 1
        p1 = s2sphere.LatLng.from_degrees(lat, lng)
        p2 = s2sphere.LatLng.from_degrees(lat, lng)
        covering = region_cover.get_covering(s2sphere.LatLngRect.from_point_pair(p1, p2))
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
    def calc_s2_cells(north, south, west, east, cell_size=16):
        centers_in_area = []
        region = s2sphere.RegionCoverer()
        region.min_level = cell_size
        region.max_level = cell_size
        p1 = s2sphere.LatLng.from_degrees(north, west)
        p2 = s2sphere.LatLng.from_degrees(south, east)
        cell_ids = region.get_covering(
            s2sphere.LatLngRect.from_point_pair(p1, p2))
        log.debug('Detecting ' + str(len(cell_ids)) +
              ' L{} Cells in Area'.format(str(cell_size)))
        for cell_id in cell_ids:
            split_cell_id = str(cell_id).split(' ')
            position = S2Helper.get_position_from_cell(int(split_cell_id[1], 16))
            centers_in_area.append([position[0], position[1]])
            # calc_route_data.append(str(position[0]) + ', ' + str(position[1]))

        return centers_in_area

    @staticmethod
    def get_position_from_cell(cell_id):
        cell = s2sphere.CellId(id_=int(cell_id)).to_lat_lng()
        return s2sphere.math.degrees(cell.lat().radians), \
               s2sphere.math.degrees(cell.lng().radians), 0
               
    @staticmethod    
    def get_s2_cells_from_fence(geofence, cell_size=16):
        _geofence = geofence
        log.warning("Calculating corners of fences")
        south, east, north, west= _geofence.get_polygon_from_fence()
        calc_route_data = []
        region = s2sphere.RegionCoverer()
        region.min_level = cell_size
        region.max_level = cell_size
        p1 = s2sphere.LatLng.from_degrees(north, west)
        p2 = s2sphere.LatLng.from_degrees(south, east)
        log.warning("Calculating coverage of region")
        cell_ids = region.get_covering(
            s2sphere.LatLngRect.from_point_pair(p1, p2))

        log.warning("Iterating cell_ids")
        for cell_id in cell_ids:
            split_cell_id = str(cell_id).split(' ')
            position = S2Helper.middle_of_cell(int(split_cell_id[1], 16))
            calc_route_data.append([position[0], position[1]])
        log.debug('Detecting ' + str(len(calc_route_data)) +
                 ' L{} Cells in Area'.format(str(cell_size)))

        return calc_route_data
