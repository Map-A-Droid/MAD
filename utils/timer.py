import logging
import datetime, time

from threading import Thread

log = logging.getLogger(__name__)

class Timer(object):
    def __init__(self, sleep, id, sleeptime='0'):
        self._switch = False
        
        self._id = id
        self._sleep = sleep
        self._sleeptime = sleeptime
        
        log.info('[%s] - check for Sleeptimer' % str(self._id))
        
        if self._sleep:
            t_sleeptimer = Thread(name='sleeptimer',
                                  target=self.sleeptimer)
            t_sleeptimer.daemon = True
            t_sleeptimer.start()
        
    def set_sleep(self, switch):
        log.info('[%s] - set sleep: %s' % (str(self._id), str(switch)))
        self._switch = switch
        return
        
    def get_sleep(self):
        return self._switch

    def sleeptimer(self):
        log.info('[%s] - Starting Sleeptimer' % str(self._id))
        sleeptime = self._sleeptime
        sts1 = sleeptime[0].split(':')
        sts2 = sleeptime[1].split(':')
        while True:
            tmFrom = datetime.datetime.now().replace(hour=int(sts1[0]),minute=int(sts1[1]),second=0,microsecond=0)
            tmTil = datetime.datetime.now().replace(hour=int(sts2[0]),minute=int(sts2[1]),second=0,microsecond=0)
            tmNow = datetime.datetime.now()

            # check if current time is past start time
            # and the day has changed already. thus shift
            # start time back to the day before
            if tmFrom > tmTil > tmNow:
                tmFrom = tmFrom + datetime.timedelta(days=-1)

            # check if start time is past end time thus
            # shift start time one day into the future
            if tmTil < tmFrom:
                tmTil = tmTil + datetime.timedelta(days=1)

            log.debug("[%s] - Time now: %s" % (tmNow, str(self._id)))
            log.debug("[%s] - Time From: %s" % (tmFrom, str(self._id)))
            log.debug("[%s] - Time Til: %s" % (tmTil, str(self._id)))

            if tmFrom <= tmNow < tmTil:
                log.info('[%s] - Going to sleep - bye bye'% str(self._id))
                self.set_sleep(True)

                while self.get_sleep():
                    log.info("[%s] - Currently sleeping...zzz" % str(self._id))
                    log.debug("[%s] - Time now: %s" % (tmNow, str(self._id)))
                    log.debug("[%s] - Time From: %s" % (tmFrom, str(self._id)))
                    log.debug("[%s] - Time Til: %s" % (tmTil, str(self._id)))
                    tmNow = datetime.datetime.now()
                    log.info('[%s] - Still sleeping, current time... %s' % (str(self._id), str(tmNow.strftime("%H:%M"))))
                    if tmNow >= tmTil:
                        log.warning('[%s] - sleeptimer: Wakeup - here we go ...' % str(self._id))
                        self.set_sleep(False)
                        break
                    time.sleep(30)
            time.sleep(30)