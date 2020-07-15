import time
from threading import Thread
from mapadroid.utils.logging import get_logger, LoggerEnums


logger = get_logger(LoggerEnums.utils)


class Event(object):
    def __init__(self, args, dbwrapper):
        self.args = args
        self._dbwrapper = dbwrapper
        self._event_id: int = 1
        self._lure_duration: int = 30

    def event_checker(self):
        while True:
            self._event_id, self._lure_duration = self._dbwrapper.get_current_event()
            self._dbwrapper.set_event_id(self._event_id)
            self._dbwrapper.set_event_lure_duration(self._lure_duration)
            time.sleep(60)

    def start_event_checker(self):
        if not self.args.no_event_checker:
            event_thread = Thread(name='system', target=self.event_checker)
            event_thread.daemon = True
            event_thread.start()

    def get_current_event_id(self):
        return self._event_id
