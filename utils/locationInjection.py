import time
import logging
from threading import Lock

log = logging.getLogger(__name__)

# Allow manual overrides of the routing (by clicking on the madmin map, or inserting into db table).
# This singleton class keeps a list of active injection requests (updated at most once every 5 seconds),
# which route managers can pull from.

class LocationInjection:
    def __init__(self, db_wrapper):
        self.db_wrapper = db_wrapper
        self.update_interval = 5
        self.last_update = 0
        self.queue = []
        self.mutex = Lock()

    def get_injection(self, mode):
        if time.time() - self.update_interval > self.last_update:
            log.debug("Reloading location injections")
            self.mutex.acquire()
            self.queue = self.db_wrapper.get_location_injections()
            self.last_update = time.time()
            self.mutex.release()

        claimed = None

        for index, item in enumerate(self.queue):
            (id, lat, lng, item_mode) = item
            if mode == item_mode or item_mode is None:
                self.queue.pop(index)
                self.db_wrapper.remove_location_injection(id)
                claimed = [lat, lng]
                break

        return claimed