import collections
from typing import NamedTuple


class Location(NamedTuple):
    lat: float
    lng: float


# Location = collections.namedtuple('Location', lat=float, lng=float)
Relation = collections.namedtuple(
    'Relation', ['other_event', 'distance', 'timedelta'])
Trash = collections.namedtuple('Trash', ['x', 'y'])
Login_PTC = collections.namedtuple('PTC', ['username', 'password'])
Login_GGL = collections.namedtuple('GGL', ['username'])
