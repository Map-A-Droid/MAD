import math


def getDistanceOfTwoPointsInMeters(startLat, startLng, destLat, destLng):
    # approximate radius of earth in km
    R = 6373.0

    lat1 = math.radians(startLat)
    lon1 = math.radians(startLng)
    lat2 = math.radians(destLat)
    lon2 = math.radians(destLng)

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance = R * c

    distanceInMeters = distance * 1000
    return distanceInMeters
