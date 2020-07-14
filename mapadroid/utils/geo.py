import math

from mapadroid.utils.collections import Location


def get_lat_lng_offsets_by_distance(distance):
    earth = 6373.0
    meters = (1 / ((2 * math.pi / 360) * earth)) / 1000  # meter in degree
    lat_offset = distance * meters
    lng_offset = (distance * meters) / math.cos((math.pi / 180))
    return lat_offset, lng_offset


def get_distance_of_two_points_in_meters(startLat, startLng, destLat, destLng):
    # approximate radius of earth in km
    earth_radius = 6373.0

    lat1 = math.radians(startLat)
    lon1 = math.radians(startLng)
    lat2 = math.radians(destLat)
    lon2 = math.radians(destLng)

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    angle = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    circ = 2 * math.atan2(math.sqrt(angle), math.sqrt(1 - angle))

    distance = earth_radius * circ

    distanceInMeters = distance * 1000
    return distanceInMeters


def get_middle_of_coord_list(list_of_coords):
    if len(list_of_coords) == 1:
        return list_of_coords[0]

    coord_x = 0
    coord_y = 0
    coord_z = 0

    for coord in list_of_coords:
        # transform to radians...
        lat_rad = math.radians(coord.lat)
        lng_rad = math.radians(coord.lng)

        coord_x += math.cos(lat_rad) * math.cos(lng_rad)
        coord_y += math.cos(lat_rad) * math.sin(lng_rad)
        coord_z += math.sin(lat_rad)

    amount_of_coords = len(list_of_coords)
    coord_x = coord_x / amount_of_coords
    coord_y = coord_y / amount_of_coords
    coord_z = coord_z / amount_of_coords
    central_lng = math.atan2(coord_y, coord_x)
    central_square_root = math.sqrt(coord_x * coord_x + coord_y * coord_y)
    central_lat = math.atan2(coord_z, central_square_root)

    return Location(math.degrees(central_lat), math.degrees(central_lng))
