import datetime
import logging
import time
from threading import Thread

log = logging.getLogger(__name__)


class Timer(object):
    def __init__(self, switch, id, switchtime='0'):
        self._switchmode = False

        self._id = id
        self._switch = switch
        self._switchtime = switchtime

        log.info('[%s] - check for Switchtimer' % str(self._id))

        if self._switch:
            log.info('[%s] - starting Switchtimer' % str(self._id))
            t_switchtimer = Thread(name='switchtimer',
                                  target=self.switchtimer)
            t_switchtimer.daemon = True
            t_switchtimer.start()
        else:
            log.info('[%s] - no Switchtimer needed' % str(self._id))
        

    def set_switch(self, switch):
        log.info('[%s] - set switch: %s' % (str(self._id), str(switch)))
        self._switchmode = switch
        return

    def get_switch(self):
        return self._switchmode

    def switchtimer(self):
        switchtime = self._switchtime
        sts1 = switchtime[0].split(':')
        sts2 = switchtime[1].split(':')
        while True:
            tmFrom = datetime.datetime.now().replace(
                hour=int(sts1[0]), minute=int(sts1[1]), second=0, microsecond=0)
            tmTil = datetime.datetime.now().replace(
                hour=int(sts2[0]), minute=int(sts2[1]), second=0, microsecond=0)
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

            if tmFrom <= tmNow < tmTil:
                log.info('[%s] - Switching Mode' % str(self._id))
                self.set_switch(True)

                while self.get_switch():
                    log.info("[%s] - Currently in switchmode" % str(self._id))
                    if tmNow >= tmTil:
                        log.warning(
                            '[%s] - Switching back - here we go ...' % str(self._id))
                        self.set_switch(False)
                        break
                    time.sleep(30)
            time.sleep(30)
