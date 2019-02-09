import math

from utils.collections import Location


def get_distance_of_two_points_in_meters(startLat, startLng, destLat, destLng):
    # approximate radius of earth in km
    R = 6373.0

    lat1 = math.radians(startLat)
    lon1 = math.radians(startLng)
    lat2 = math.radians(destLat)
    lon2 = math.radians(destLng)

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * \
        math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance = R * c

    distanceInMeters = distance * 1000
    return distanceInMeters


def get_middle_of_coord_list(list_of_coords):
    if len(list_of_coords) == 1:
        return list_of_coords[0]

    x = 0
    y = 0
    z = 0

    for coord in list_of_coords:
        # transform to radians...
        lat_rad = math.radians(coord.lat)
        lng_rad = math.radians(coord.lng)

        x += math.cos(lat_rad) * math.cos(lng_rad)
        y += math.cos(lat_rad) * math.sin(lng_rad)
        z += math.sin(lat_rad)

    amount_of_coords = len(list_of_coords)
    x = x / amount_of_coords
    y = y / amount_of_coords
    z = z / amount_of_coords
    central_lng = math.atan2(y, x)
    central_square_root = math.sqrt(x * x + y * y)
    central_lat = math.atan2(z, central_square_root)

    return Location(math.degrees(central_lat), math.degrees(central_lng))
