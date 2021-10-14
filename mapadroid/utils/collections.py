import collections
from typing import NamedTuple, Union

import ujson
from orjson import orjson


class Location(NamedTuple):
    lat: float
    lng: float

    def to_json(self) -> str:
        return ujson.dumps(self)

    @staticmethod
    def from_json(json_str: Union[bytes, str]):
        raw = orjson.loads(json_str)
        return Location(raw[0], raw[1])


# Location = collections.namedtuple('Location', lat=float, lng=float)
Relation = collections.namedtuple(
    'Relation', ['other_event', 'distance', 'timedelta'])
ScreenCoordinates = collections.namedtuple('ScreenCoordinates', ['x', 'y'])
Login_PTC = collections.namedtuple('PTC', ['username', 'password'])
Login_GGL = collections.namedtuple('GGL', ['username'])
