import logging
import time
from datetime import datetime

log = logging.getLogger(__name__)
sleep = False


class SleepTime:

    @staticmethod
    def sleeptimer(sleeptime):
        global sleep
        while True:
            sleep_time_start = sleeptime[0].split(':')
            sleep_time_end = sleeptime[1].split(':')

            time_from = datetime.now().replace(hour=int(sleep_time_start[0]),
                                               minute=int(sleep_time_start[1]),
                                               second=0, microsecond=0)
            time_until = datetime.now().replace(hour=int(sleep_time_end[0]),
                                                minute=int(sleep_time_end[1]),
                                                second=0, microsecond=0)
            time_now = datetime.now()

            # special check. let's say we want to start at 21:00 until 05:00.
            # if you restart the server after 24:00, both datetime objects will
            # have the same day thus the sleep timer won't start. This
            # little snippet will set the day of time_from to the day before.
            if time_from > time_until > time_now:
                time_from = time_from.replace(day=time_from.day-1)

            log.debug("Sleep time from: %s", time_from)
            log.debug("Sleep time until: %s", time_until)
            log.debug("Sleep time now: %s", time_now)

            if time_from <= time_now < time_until and not sleep:
                log.info('Sleep timer active from %s to %s', time_from,
                         time_until)
                sleep = True
            elif time_now >= time_until and sleep:
                log.info("Sleep timer stopped. Daytime reached.")
                sleep = False

            time.sleep(15)
