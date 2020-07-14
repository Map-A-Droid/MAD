import time
from multiprocessing import Lock, Queue
from multiprocessing.managers import SyncManager
from queue import Empty
from threading import Thread, Event
from typing import Dict
from mapadroid.db.DbStatsSubmit import DbStatsSubmit
from mapadroid.mitm_receiver.PlayerStats import PlayerStats
from mapadroid.utils.MappingManager import MappingManager
from mapadroid.utils.collections import Location
from mapadroid.utils.walkerArgs import parseArgs
from mapadroid.utils.logging import get_logger, LoggerEnums, get_origin_logger


logger = get_logger(LoggerEnums.mitm)
args = parseArgs()


class MitmMapperManager(SyncManager):
    pass


class MitmMapper(object):
    def __init__(self, mapping_manager: MappingManager, db_stats_submit: DbStatsSubmit):
        self.__mapping = {}
        self.__playerstats: Dict[str, PlayerStats] = {}
        self.__mapping_mutex = Lock()
        self.__mapping_manager: MappingManager = mapping_manager
        self.__injected = {}
        self.__last_cellsid = {}
        self.__last_possibly_moved = {}
        self.__application_args = args
        self._db_stats_submit: DbStatsSubmit = db_stats_submit
        self.__playerstats_db_update_stop: Event = Event()
        self.__playerstats_db_update_queue: Queue = Queue()
        self.__playerstats_db_update_mutex: Lock = Lock()
        pstat_args = {
            'name': 'system',
            'target': self.__internal_playerstats_db_update_consumer
        }
        self.__playerstats_db_update_consumer: Thread = Thread(**pstat_args)
        if self.__mapping_manager is not None:
            for origin in self.__mapping_manager.get_all_devicemappings().keys():
                self.__add_new_device(origin)
        self.__playerstats_db_update_consumer.daemon = True
        self.__playerstats_db_update_consumer.start()

    def __add_new_device(self, origin):
        self.__mapping[origin] = {}
        self.__playerstats[origin] = PlayerStats(origin, self.__application_args, self)
        self.__playerstats[origin].open_player_stats()

    def add_stats_to_process(self, client_id, stats, last_processed_timestamp):
        if self.__application_args.game_stats:
            with self.__playerstats_db_update_mutex:
                self.__playerstats_db_update_queue.put((client_id, stats, last_processed_timestamp))

    def __internal_playerstats_db_update_consumer(self):
        try:
            while not self.__playerstats_db_update_stop.is_set():
                if not self.__application_args.game_stats:
                    logger.info("Playerstats are disabled")
                    break
                try:
                    with self.__playerstats_db_update_mutex:
                        next_item = self.__playerstats_db_update_queue.get_nowait()
                except Empty:
                    time.sleep(0.5)
                    continue
                if next_item is not None:
                    client_id, stats, last_processed_timestamp = next_item
                    logger.info("Running stats processing on {}", client_id)
                    self.__process_stats(stats, client_id, last_processed_timestamp)
        except Exception as e:
            logger.error("Playerstats consumer stopping because of {}", e)
        logger.info("Shutting down Playerstats update consumer")

    def __process_stats(self, stats, client_id: str, last_processed_timestamp: float):
        origin_logger = get_origin_logger(logger, origin=client_id)
        origin_logger.debug('Submitting stats')
        data_send_stats = []
        data_send_location = []

        data_send_stats.append(PlayerStats.stats_complete_parser(client_id, stats, last_processed_timestamp))
        data_send_location.append(
            PlayerStats.stats_location_parser(client_id, stats, last_processed_timestamp))

        self._db_stats_submit.submit_stats_complete(data_send_stats)
        self._db_stats_submit.submit_stats_locations(data_send_location)
        if self.__application_args.game_stats_raw:
            data_send_location_raw = PlayerStats.stats_location_raw_parser(client_id, stats,
                                                                           last_processed_timestamp)
            data_send_detection_raw = PlayerStats.stats_detection_raw_parser(client_id, stats,
                                                                             last_processed_timestamp)
            self._db_stats_submit.submit_stats_locations_raw(data_send_location_raw)
            self._db_stats_submit.submit_stats_detections_raw(data_send_detection_raw)

        data_send_stats.clear()
        data_send_location.clear()

        self._db_stats_submit.cleanup_statistics()

    def shutdown(self):
        self.__playerstats_db_update_stop.set()
        self.__playerstats_db_update_consumer.join()
        self.__playerstats_db_update_queue.close()
        # self.__playerstats_db_update_queue.join()

    def get_mon_ids_iv(self, origin):
        devicemapping_of_origin = self.__mapping_manager.get_devicemappings_of(origin)
        if devicemapping_of_origin is None:
            return []
        else:
            return devicemapping_of_origin.get("mon_ids_iv", [])

    def get_levelmode(self, origin):
        device_routemananger = self.__mapping_manager.get_routemanager_name_from_device(origin)
        if device_routemananger is None:
            return False

        if self.__mapping_manager.routemanager_get_level(device_routemananger):
            return True

        return False

    def get_safe_items(self, origin):
        get_devicesettings_of_origin = self.__mapping_manager.get_devicesettings_of(origin)
        if get_devicesettings_of_origin is None:
            return []
        else:
            enhanced_mode_quest_safe_items = \
                get_devicesettings_of_origin.get("enhanced_mode_quest_safe_items", "1301, 1401,1402, 1403, 1106, "
                                                 "901, 902, 903, 501, 502, 503,"
                                                 "504, 301").split(",")

            return list(map(int, enhanced_mode_quest_safe_items))

    def request_latest(self, origin, key=None):
        origin_logger = get_origin_logger(logger, origin=origin)
        origin_logger.debug2("Request latest called")
        with self.__mapping_mutex:
            result = None
            retrieved = self.__mapping.get(origin, None)
            if retrieved is not None:
                # copy in case references are overwritten... who knows
                # TODO: double check what python does in the background
                retrieved = retrieved.copy()
            if key is None:
                result = retrieved
            elif retrieved is not None:
                result = retrieved.get(key, None)
        origin_logger.debug2("Request latest done")
        return result

    # origin, method, data, timestamp
    def update_latest(self, origin: str, key: str, values_dict, timestamp_received_raw: float = None,
                      timestamp_received_receiver: float = None, location: Location = None):
        origin_logger = get_origin_logger(logger, origin=origin)
        if timestamp_received_raw is None:
            timestamp_received_raw = time.time()

        if timestamp_received_receiver is None:
            timestamp_received_receiver = time.time()

        updated = False
        origin_logger.debug2("Trying to acquire lock and update proto {}", key)
        with self.__mapping_mutex:
            if origin not in self.__mapping.keys() and origin in self.__mapping_manager.get_all_devicemappings().keys():
                origin_logger.info("New device detected.  Setting up the device configuration")
                self.__add_new_device(origin)
            if origin in self.__mapping.keys():
                origin_logger.debug2("Updating timestamp at {} with method {} to {}", location, key,
                                     timestamp_received_raw)
                if self.__mapping.get(origin) is not None and self.__mapping[origin].get(key) is not None:
                    del self.__mapping[origin][key]
                self.__mapping[origin][key] = {}
                self.__mapping[origin]["location"] = location
                self.__mapping[origin][key]["timestamp"] = timestamp_received_raw
                self.__mapping[origin]["timestamp_last_data"] = timestamp_received_raw
                self.__mapping[origin]["timestamp_receiver"] = timestamp_received_receiver
                self.__mapping[origin][key]["values"] = values_dict
                updated = True
            else:
                origin_logger.warning("Not updating timestamp since origin is unknown")
        origin_logger.debug2("Done updating proto {}", key)
        return updated

    def set_injection_status(self, origin, status=True):
        origin_logger = get_origin_logger(logger, origin=origin)
        if origin not in self.__injected or not self.__injected[origin] and status is True:
            origin_logger.success("Worker is injected now")
        self.__injected[origin] = status

    def get_injection_status(self, origin):
        return self.__injected.get(origin, False)

    def run_stats_collector(self, origin: str):
        if self.__playerstats.get(origin, None) is not None:
            self.__playerstats.get(origin).stats_collector()

    def collect_location_stats(self, origin: str, location: Location, datarec, start_timestamp: float, positiontype,
                               rec_timestamp: float, walker, transporttype):
        if self.__playerstats.get(origin, None) is not None and location is not None:
            self.__playerstats.get(origin).stats_collect_location_data(location, datarec, start_timestamp,
                                                                       positiontype,
                                                                       rec_timestamp, walker, transporttype)

    def get_playerlevel(self, origin: str):
        if self.__playerstats.get(origin, None) is not None:
            return self.__playerstats.get(origin).get_level()
        else:
            return -1

    def get_poke_stop_visits(self, origin: str) -> int:
        if self.__playerstats.get(origin, None) is not None:
            return self.__playerstats.get(origin).get_poke_stop_visits()
        else:
            return -1

    def collect_raid_stats(self, origin: str, gym_id: str):
        if self.__playerstats.get(origin, None) is not None:
            self.__playerstats.get(origin).stats_collect_raid(gym_id)

    def collect_mon_stats(self, origin: str, encounter_id: str):
        if self.__playerstats.get(origin, None) is not None:
            self.__playerstats.get(origin).stats_collect_mon(encounter_id)

    def collect_mon_iv_stats(self, origin: str, encounter_id: str, shiny: int):
        if self.__playerstats.get(origin, None) is not None:
            self.__playerstats.get(origin).stats_collect_mon_iv(encounter_id, shiny)

    def collect_quest_stats(self, origin: str, stop_id: str):
        if self.__playerstats.get(origin, None) is not None:
            self.__playerstats.get(origin).stats_collect_quest(stop_id)

    def generate_player_stats(self, origin: str, inventory_proto: dict):
        if self.__playerstats.get(origin, None) is not None:
            self.__playerstats.get(origin).gen_player_stats(inventory_proto)

    def submit_gmo_for_location(self, origin, payload):
        origin_logger = get_origin_logger(logger, origin=origin)
        cells = payload.get("cells", None)

        if cells is None:
            return

        current_cells_id = sorted(list(map(lambda x: x['id'], cells)))
        if origin in self.__last_cellsid:
            last_cells_id = self.__last_cellsid[origin]
            self.__last_cellsid[origin] = current_cells_id
            if last_cells_id != current_cells_id:
                self.__last_possibly_moved[origin] = time.time()
        else:
            self.__last_cellsid[origin] = current_cells_id
            self.__last_possibly_moved[origin] = time.time()
        origin_logger.debug4("Done submit_gmo_for_location with {}", current_cells_id)

    def get_last_timestamp_possible_moved(self, origin):
        return self.__last_possibly_moved.get(origin, None)
