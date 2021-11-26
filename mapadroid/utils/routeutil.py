import datetime
import re
from typing import Optional

import pytz
from timezonefinder import TimezoneFinder

from mapadroid.db.model import SettingsWalkerarea
from mapadroid.utils.collections import Location
from mapadroid.utils.logging import LoggerEnums, get_logger

logger = get_logger(LoggerEnums.utils)
timezone_finder = TimezoneFinder()


def check_walker_value_type(value, location: Optional[Location] = None):
    global timezone_finder
    timezone = pytz.utc
    # If a location has been provided, the timezone that applies for that location will be used
    if location and (location.lat != 0.0 or location.lng != 0.0):
        timezone_str = timezone_finder.timezone_at(lat=location.lat, lng=location.lng)
        timezone = pytz.timezone(timezone_str)
    match = re.search(
        r'^(\d?\d:\d\d)$|^((\d?\d:\d\d)-(\d?\d:\d\d))$', value.replace(' ', ''))
    if match:
        if match.group(1):
            return check_time_till_end(value, timezone)
        elif match.group(2):
            return check_time_period(value, timezone)

    logger.error("Wrong Value for mode - check your settings! - kill Worker")
    return False


def check_time_till_end(exittime, relevant_timezone: datetime.tzinfo):
    timer = exittime.split(':')
    tm_now = datetime.datetime.now(tz=relevant_timezone)
    tm_til = tm_now.replace(hour=int(timer[0]), minute=int(timer[1]), second=0, microsecond=0)
    return tm_now < tm_til


def check_time_period(period, relevant_timezone: datetime.tzinfo):
    timer = period.split('-')
    sts1 = timer[0].replace(' ', '').split(':')
    sts2 = timer[1].replace(' ', '').split(':')
    tm_now = datetime.datetime.now(tz=relevant_timezone).replace(second=0, microsecond=0)
    tm_from = tm_now.replace(hour=int(sts1[0]), minute=int(sts1[1]))
    tm_til = tm_now.replace(hour=int(sts2[0]), minute=int(sts2[1]))

    if tm_from > tm_til:
        if tm_now < tm_from:
            tm_from = tm_from - datetime.timedelta(days=+1)
        else:
            tm_til = tm_til + datetime.timedelta(days=+1)

    return tm_from <= tm_now <= tm_til


def pre_check_value(walker_settings: SettingsWalkerarea, eventid, location: Optional[Location] = None):
    if walker_settings.eventid is not None and walker_settings.eventid != eventid:
        logger.warning("Area is used for another event - leaving now")
        return False
    if walker_settings.algo_type in ('timer', 'period', 'coords', 'idle'):
        walkervalue = walker_settings.algo_value
        if len(walkervalue) == 0:
            return True
        return check_walker_value_type(walkervalue, location)
    return True
