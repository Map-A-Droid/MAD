import collections
from typing import NamedTuple

import ujson


class Location(NamedTuple):
    lat: float
    lng: float

    def to_json(self) -> str:
        return ujson.dumps(self, default=lambda o: o.__dict__, sort_keys=True)

    @staticmethod
    def from_json(json_str: str):
        raw = ujson.loads(json_str)
        return Location(raw[0], raw[1])


# Location = collections.namedtuple('Location', lat=float, lng=float)
Relation = collections.namedtuple(
    'Relation', ['other_event', 'distance', 'timedelta'])
ScreenCoordinates = collections.namedtuple('ScreenCoordinates', ['x', 'y'])
Login_PTC = collections.namedtuple('PTC', ['username', 'password'])
Login_GGL = collections.namedtuple('GGL', ['username'])
