import collections
import dataclasses
from typing import Union

from orjson import orjson


@dataclasses.dataclass(frozen=True, eq=True)
class Location:
    lat: float
    lng: float

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


Relation = collections.namedtuple(
    'Relation', ['other_event', 'distance', 'timedelta'])
ScreenCoordinates = collections.namedtuple('ScreenCoordinates', ['x', 'y'])
Login_PTC = collections.namedtuple('PTC', ['username', 'password'])
Login_GGL = collections.namedtuple('GGL', ['username'])
