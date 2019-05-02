import datetime
import re

from utils.logging import logger


def check_walker_value_type(value, walker_start_time):
    match = re.search(
        r'^(\d?\d:\d\d)$|^((\d?\d:\d\d)-(\d?\d:\d\d))$', value.replace(' ', ''))
    if match:
        if match.group(1):
            return check_time_till_end(value, walker_start_time)
        elif match.group(2):
            return check_time_period(value)

    logger.error("Wrong Value for mode - check your settings! - kill Worker")
    return False


def check_time_till_end(exittime, walker_start_time):
    timer = exittime.split(':')
    hour = walker_start_time.strftime("%H")
    minute = walker_start_time.strftime("%M")
    tmNow = datetime.datetime.now()
    tmFrom = datetime.datetime.now().replace(
        hour=int(hour), minute=int(minute), second=0, microsecond=0)
    tmTil = datetime.datetime.now().replace(
        hour=int(timer[0]), minute=int(timer[1]), second=0, microsecond=0)
    if tmFrom > tmTil > tmNow:
        tmFrom = tmFrom + datetime.timedelta(days=-1)
    if tmTil < tmFrom:
        tmTil = tmTil + datetime.timedelta(days=1)
    if tmFrom <= tmNow < tmTil:
        return True
    else:
        return False


def check_time_period(period):
    timer = period.split('-')
    sts1 = timer[0].replace(' ', '').split(':')
    sts2 = timer[1].replace(' ', '').split(':')
    tmFrom = datetime.datetime.now().replace(
        hour=int(sts1[0]), minute=int(sts1[1]), second=0, microsecond=0)
    tmTil = datetime.datetime.now().replace(
        hour=int(sts2[0]), minute=int(sts2[1]), second=0, microsecond=0)
    tmNow = datetime.datetime.now()
    if tmFrom > tmTil > tmNow:
        tmFrom = tmFrom + datetime.timedelta(days=-1)
    if tmTil < tmFrom:
        tmTil = tmTil + datetime.timedelta(days=1)
    if tmFrom <= tmNow < tmTil:
        return True
    else:
        return False


def pre_check_value(walker_settings):
    walkertype = walker_settings['walkertype']
    if walkertype in ('timer', 'period', 'coords', 'idle'):
        walkervalue = walker_settings['walkervalue']
        if len(walkervalue) == 0:
            return True
        return check_walker_value_type(walkervalue, datetime.datetime.now())
    return True


def check_max_walkers_reached(walker_settings, routemanager):
    walkermax = walker_settings.get('walkermax', False)
    if not walkermax:
        return True

    reg_workers = routemanager.get_registered_workers()

    if int(reg_workers) > int(walkermax):
        return False

    return True
