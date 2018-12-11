import logging
from threading import Lock


log = logging.getLogger(__name__)


class ReceivedMapper(object):
    def __init__(self, device_mappings):
        self.__mapping = {}
        self.__mapping_mutex = Lock()
        if device_mappings is not None:
            for origin in device_mappings.keys():
                self.__mapping[origin] = {}

    def request_latest(self, origin):
        self.__mapping_mutex.acquire()
        retrieved = self.__mapping.get(origin, None).copy()
        self.__mapping_mutex.release()
        return retrieved

    def update_retrieved(self, origin, method, data, timestamp):
        updated = False
        self.__mapping_mutex.acquire()
        if origin in self.__mapping.keys():
            log.debug("Updating timestamp of %s with method %s to %s" % (str(origin), str(method), str(timestamp)))
            self.__mapping[origin][method] = {}
            self.__mapping[origin][method]["timestamp"] = timestamp
            self.__mapping[origin][method]["data"] = data
            updated = True
        else:
            log.warning("Not updating timestamp of %s since origin is unknown" % str(origin))
        self.__mapping_mutex.release()
        return updated
