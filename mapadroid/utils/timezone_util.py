import pytz
from timezonefinder import TimezoneFinder

from mapadroid.utils.collections import Location

timezone_finder = TimezoneFinder()


def get_timezone_at(location: Location) -> pytz.BaseTzInfo:
    timezone_str = timezone_finder.timezone_at(lat=location.lat, lng=location.lng)
    return pytz.timezone(timezone_str)
