import logging
from threading import Lock


log = logging.getLogger(__name__)


class MitmMapper(object):
    def __init__(self, device_mappings):
        self.__mapping = {}
        self.__mapping_mutex = Lock()
        if device_mappings is not None:
            for origin in device_mappings.keys():
                self.__mapping[origin] = {}

    def request_latest(self, origin, key):
        self.__mapping_mutex.acquire()
        result = None
        retrieved = self.__mapping.get(origin, None).copy()
        if retrieved is not None:
            result = retrieved.get(key, None)
        self.__mapping_mutex.release()
        return retrieved

    # origin, method, data, timestamp
    def update_latest(self, origin, timestamp, key, values_dict):
        updated = False
        self.__mapping_mutex.acquire()
        if origin in self.__mapping.keys():
            log.debug("Updating timestamp of %s with method %s to %s" % (str(origin), str(key), str(timestamp)))
            self.__mapping[origin][key] = {}
            self.__mapping[origin][key]["timestamp"] = timestamp
            self.__mapping[origin][key]["values"] = values_dict
            updated = True
        else:
            log.warning("Not updating timestamp of %s since origin is unknown" % str(origin))
        self.__mapping_mutex.release()
        return updated
