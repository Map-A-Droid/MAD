import logging
from threading import Lock
from utils.stats import PlayerStats

log = logging.getLogger(__name__)


class MitmMapper(object):
    def __init__(self, device_mappings):
        self.__mapping = {}
        self.playerstats = {}
        self.__mapping_mutex = Lock()
        self._device_mappings = device_mappings
        if device_mappings is not None:
            for origin in device_mappings.keys():
                self.__mapping[origin] = {}
                self.playerstats[origin] = PlayerStats(origin)
                self.playerstats[origin].open_player_stats()

    def get_mon_ids_iv(self, origin):
        if self._device_mappings is None or origin not in self._device_mappings.keys():
            return []
        else:
            return self._device_mappings[origin].get("mon_ids_iv", [])

    def request_latest(self, origin, key=None):
        self.__mapping_mutex.acquire()
        result = None
        retrieved = self.__mapping.get(origin, None)
        if retrieved is not None:
            # copy in case references are overwritten... who knows TODO: double check what python does in the background
            retrieved = retrieved.copy()
        if key is None:
            result = retrieved
        elif retrieved is not None:
            result = retrieved.get(key, None)
        self.__mapping_mutex.release()
        return result

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
