import datetime
import re

from mapadroid.db.model import SettingsWalkerarea
from mapadroid.utils.logging import LoggerEnums, get_logger

logger = get_logger(LoggerEnums.utils)


def check_walker_value_type(value):
    match = re.search(
        r'^(\d?\d:\d\d)$|^((\d?\d:\d\d)-(\d?\d:\d\d))$', value.replace(' ', ''))
    if match:
        if match.group(1):
            return check_time_till_end(value)
        elif match.group(2):
            return check_time_period(value)

    logger.error("Wrong Value for mode - check your settings! - kill Worker")
    return False


def check_time_till_end(exittime):
    timer = exittime.split(':')
    tm_now = datetime.datetime.now()
    tm_til = tm_now.replace(hour=int(timer[0]), minute=int(timer[1]), second=0, microsecond=0)
    return tm_now < tm_til


def check_time_period(period):
    timer = period.split('-')
    sts1 = timer[0].replace(' ', '').split(':')
    sts2 = timer[1].replace(' ', '').split(':')
    tm_now = datetime.datetime.now().replace(second=0, microsecond=0)
    tm_from = tm_now.replace(hour=int(sts1[0]), minute=int(sts1[1]))
    tm_til = tm_now.replace(hour=int(sts2[0]), minute=int(sts2[1]))

    if tm_from > tm_til:
        if tm_now < tm_from:
            tm_from = tm_from - datetime.timedelta(days=+1)
        else:
            tm_til = tm_til + datetime.timedelta(days=+1)

    return tm_from <= tm_now <= tm_til


def pre_check_value(walker_settings: SettingsWalkerarea, eventid):
    if walker_settings.eventid is not None and walker_settings.eventid != eventid:
        logger.warning("Area is used for another event - leaving now")
        return False
    if walker_settings.algo_type in ('timer', 'period', 'coords', 'idle'):
        walkervalue = walker_settings.algo_value
        if len(walkervalue) == 0:
            return True
        return check_walker_value_type(walkervalue)
    return True
