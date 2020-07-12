import datetime
import re
from mapadroid.utils.logging import get_logger, LoggerEnums


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
    tmNow = datetime.datetime.now()
    tmTil = tmNow.replace(
        hour=int(timer[0]), minute=int(timer[1]), second=0, microsecond=0)
    return tmNow < tmTil


def check_time_period(period):
    timer = period.split('-')
    sts1 = timer[0].replace(' ', '').split(':')
    sts2 = timer[1].replace(' ', '').split(':')
    tmNow = datetime.datetime.now().replace(second=0, microsecond=0)
    tmFrom = tmNow.replace(hour=int(sts1[0]), minute=int(sts1[1]))
    tmTil = tmNow.replace(hour=int(sts2[0]), minute=int(sts2[1]))

    if tmFrom > tmTil:
        if tmNow < tmFrom:
            tmFrom = tmFrom - datetime.timedelta(days=+1)
        else:
            tmTil = tmTil + datetime.timedelta(days=+1)

    return tmFrom <= tmNow <= tmTil


def pre_check_value(walker_settings, eventid):
    walkertype = walker_settings['walkertype']
    walkereventid = walker_settings.get('eventid', None)
    if walkereventid is not None and walkereventid != eventid:
        logger.warning("Area is used for another event - leaving now")
        return False
    if walkertype in ('timer', 'period', 'coords', 'idle'):
        walkervalue = walker_settings['walkervalue']
        if len(walkervalue) == 0:
            return True
        return check_walker_value_type(walkervalue)
    return True
