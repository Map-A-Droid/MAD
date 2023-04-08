import collections
from typing import Any, Union

from orjson import orjson


class Location:
    __slots__ = 'lat', 'lng'
    lat: float
    lng: float

    def __init__(self, lat: float, lng: float):
        self.lat = lat
        self.lng = lng

    def __getitem__(self, index):
        return self.lat if index == 0 else self.lng

    def to_json(self) -> bytes:
        return orjson.dumps(self)

    def __str__(self) -> str:
        return f"{self.lat}, {self.lng}"

    @staticmethod
    def from_json(json_str: Union[bytes, str]):
        raw = orjson.loads(json_str)
        if isinstance(raw, list):
            return Location(raw[0], raw[1])
        elif isinstance(raw, dict):
            lat = raw.get("lat", 0.0)
            lng = raw.get("lng", 0.0)
            return Location(lat, lng)
        else:
            return None


class Relation:
    __slots__ = 'other_event', 'distance', 'timedelta'
    other_event: Any
    distance: float
    timedelta: int

    def __init__(self, other_event: Any, distance: float, timedelta: int):
        self.other_event = other_event
        self.distance = distance
        self.timedelta = timedelta

    def __getitem__(self, index):
        if index == 0:
            return self.other_event
        elif index == 1:
            return self.distance
        else:
            return self.timedelta


ScreenCoordinates = collections.namedtuple('ScreenCoordinates', ['x', 'y'])
Login_PTC = collections.namedtuple('PTC', ['username', 'password'])
Login_GGL = collections.namedtuple('GGL', ['username'])
