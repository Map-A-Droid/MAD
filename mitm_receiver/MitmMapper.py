import time
from multiprocessing import Lock
from multiprocessing.managers import SyncManager

from db.DbFactory import DbFactory
from db.dbWrapperBase import DbWrapperBase
from utils.collections import Location
from utils.logging import logger
from utils.stats import PlayerStats
from utils.walkerArgs import parseArgs

args = parseArgs()


class MitmMapperManager(SyncManager):
    pass


class MitmMapper(object):
    def __init__(self, device_mappings):
        self.__mapping = {}
        self.__playerstats = {}
        self.__mapping_mutex = Lock()
        self.__device_mappings = device_mappings
        self.__injected = {}
        self.__application_args = args
        self.__db_wrapper: DbWrapperBase = DbFactory.get_wrapper(self.__application_args)
        if device_mappings is not None:
            for origin in device_mappings.keys():
                self.__mapping[origin] = {}
                self.__playerstats[origin] = PlayerStats(origin, self.__application_args, self.__db_wrapper)
                self.__playerstats[origin].open_player_stats()

    def get_mon_ids_iv(self, origin):
        if self.__device_mappings is None or origin not in self.__device_mappings.keys():
            return []
        else:
            return self.__device_mappings[origin].get("mon_ids_iv", [])

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
    def update_latest(self, origin, key, values_dict, timestamp_received_raw: float = time.time(),
                      timestamp_received_receiver: float = time.time()):
        updated = False
        self.__mapping_mutex.acquire()
        if origin in self.__mapping.keys():
            logger.debug("Updating timestamp of {} with method {} to {}", str(
                origin), str(key), str(timestamp_received_raw))
            if self.__mapping.get(origin) is not None and self.__mapping[origin].get(key) is not None:
                del self.__mapping[origin][key]
            self.__mapping[origin][key] = {}
            self.__mapping[origin][key]["timestamp"] = timestamp_received_raw
            self.__mapping[origin]["timestamp_last_data"] = timestamp_received_raw
            self.__mapping[origin]["timestamp_receiver"] = timestamp_received_receiver
            self.__mapping[origin][key]["values"] = values_dict
            updated = True
        else:
            logger.warning(
                "Not updating timestamp of {} since origin is unknown", str(origin))
        self.__mapping_mutex.release()
        return updated

    def set_injection_status(self, origin, status=True):
        self.__injected[origin] = status

    def get_injection_status(self, origin):
        return self.__injected.get(origin, False)

    def run_stats_collector(self, origin: str):
        if self.__playerstats.get(origin, None) is not None:
            self.__playerstats.get(origin).stats_collector()

    def collect_location_stats(self, origin: str, location: Location, datarec, start_timestamp: float, type,
                               rec_timestamp: float, walker, transporttype):
        if self.__playerstats.get(origin, None) is not None:
            self.__playerstats.get(origin).stats_collect_location_data(location, datarec, start_timestamp, type,
                                                                       rec_timestamp, walker, transporttype)

    def get_playerlevel(self, origin: str):
        if self.__playerstats.get(origin, None) is not None:
            return self.__playerstats.get(origin).get_level()
        else:
            return -1

    def collect_raid_stats(self, origin: str, gym_id: str):
        if self.__playerstats.get(origin, None) is not None:
            self.__playerstats.get(origin).stats_collect_raid(gym_id)

    def collect_mon_stats(self, origin: str, encounter_id: str):
        if self.__playerstats.get(origin, None) is not None:
            self.__playerstats.get(origin).stats_collect_mon(encounter_id)

    def collect_mon_iv_stats(self, origin: str, encounter_id: str):
        if self.__playerstats.get(origin, None) is not None:
            self.__playerstats.get(origin).stats_collect_mon_iv(encounter_id)

    def collect_quest_stats(self, origin: str, stop_id: str):
        if self.__playerstats.get(origin, None) is not None:
            self.__playerstats.get(origin).stats_collect_quest(stop_id)

    def generate_player_stats(self, origin: str, inventory_proto: dict):
        if self.__playerstats.get(origin, None) is not None:
            self.__playerstats.get(origin).gen_player_stats(inventory_proto)


MitmMapperManager.register('MitmMapper', MitmMapper)
