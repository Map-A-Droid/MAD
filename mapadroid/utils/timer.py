import datetime
import time
from threading import Event, Thread
from mapadroid.utils.logging import get_logger, LoggerEnums


logger = get_logger(LoggerEnums.utils)


class Timer(object):
    def __init__(self, switch, timer_id, switchtime='0'):
        self._switchmode = False

        self._id = timer_id
        self._switch = switch
        self._switchtime = switchtime
        self.__stop_switchtimer = Event()
        self.__t_switchtimer = None
        logger.info('[{}] - check for Switchtimer', str(self._id))

        self.__t_switchtimer = None
        if self._switch:
            self.__t_switchtimer = Thread(name='switchtimer_%s' % str(self._id),
                                          target=self.switchtimer)
            self.__t_switchtimer.daemon = True
            self.__t_switchtimer.start()

    def set_switch(self, switch):
        logger.info('[{}] - set switch: {}', str(self._id), str(switch))
        self._switchmode = switch
        return

    def stop_switch(self):
        if not self.__stop_switchtimer.is_set() and self.__t_switchtimer is not None:
            logger.info("[{}] stopping switchtimer", str(self._id))
            self.__stop_switchtimer.set()
            self.__t_switchtimer.join()
            logger.info("[{}] switchtimer stopped", str(self._id))

    def get_switch(self):
        return self._switchmode

    def switchtimer(self):
        logger.info('[{}] - Starting Switchtimer', str(self._id))
        switchtime = self._switchtime
        sts1 = switchtime[0].split(':')
        sts2 = switchtime[1].split(':')
        while not self.__stop_switchtimer.is_set():
            tm_from = datetime.datetime.now().replace(
                hour=int(sts1[0]), minute=int(sts1[1]), second=0, microsecond=0)
            tm_til = datetime.datetime.now().replace(
                hour=int(sts2[0]), minute=int(sts2[1]), second=0, microsecond=0)
            tm_now = datetime.datetime.now()

            # check if current time is past start time
            # and the day has changed already. thus shift
            # start time back to the day before
            if tm_from > tm_til > tm_now:
                tm_from = tm_from + datetime.timedelta(days=-1)

            # check if start time is past end time thus
            # shift start time one day into the future
            if tm_til < tm_from:
                tm_til = tm_til + datetime.timedelta(days=1)

            if tm_from <= tm_now < tm_til:
                logger.info('[{}] - Switching Mode', str(self._id))
                self.set_switch(True)

                while self.get_switch():
                    tm_now = datetime.datetime.now()
                    logger.info("[{}] - Currently in switchmode",
                                str(self._id))
                    if tm_now >= tm_til:
                        logger.warning('[{}] - Switching back - here we go ...', str(self._id))
                        self.set_switch(False)
                    if self.__stop_switchtimer.is_set():
                        logger.info(
                            "[{}] switchtimer stopping in switchmode", str(self._id))
                        self.set_switch(False)
                    time.sleep(30)
            time.sleep(30)

        logger.info("[{}] switchtimer stopping", str(self._id))
