import datetime
import json
import os
import time
from math import floor
from multiprocessing import Lock
from pathlib import Path

from mapadroid.mitm_receiver import MitmMapper
from mapadroid.utils.logging import logger


class PlayerStats(object):
    def __init__(self, id, application_args, mitm_mapper_parent: MitmMapper):
        self._id = id
        self.__application_args = application_args
        self._level: int = 0
        self._last_action_time = 0
        self._last_period = 0
        self.__stats_collected: dict = {}
        self._stats_collector_start = True
        self._last_processed_timestamp = 0
        self._stats_period = 0
        self._generate_stats = application_args.game_stats
        self.__mapping_mutex = Lock()
        self.__mitm_mapper_parent: MitmMapper = mitm_mapper_parent
        self._poke_stop_visits: int = 0

    def set_level(self, level: int):
        logger.debug('[{}] - set level {}', str(self._id), str(level))
        self._level = int(level)
        return True

    def get_level(self) -> int:
        return self._level

    def set_poke_stop_visits(self, visits: int):
        logger.debug('[{}] - set pokestops visited {}', str(self._id), str(visits))
        self._poke_stop_visits = visits
        return True

    def get_poke_stop_visits(self) -> int:
        return self._poke_stop_visits

    def gen_player_stats(self, data: dict):
        if 'inventory_delta' not in data:
            logger.debug('gen_player_stats cannot generate new stats')
            return
        stats = data['inventory_delta'].get("inventory_items", None)
        if len(stats) > 0:
            for data_inventory in stats:
                player_stats = data_inventory['inventory_item_data']['player_stats']
                player_level = player_stats['level']
                if int(player_level) > 0:
                    logger.debug('{{gen_player_stats}} saving new playerstats')
                    self.set_level(int(player_level))

                    data = {self._id: []}
                    data[self._id].append({
                        'level': str(player_stats['level']),
                        'experience': str(player_stats['experience']),
                        'km_walked': str(player_stats['km_walked']),
                        'pokemons_encountered': str(player_stats['pokemons_encountered']),
                        'poke_stop_visits': str(player_stats['poke_stop_visits'])
                    })
                    with open(os.path.join(self.__application_args.file_path, str(self._id) + '.stats'),
                              'w') as outfile:
                        json.dump(data, outfile, indent=4, sort_keys=True)

    def open_player_stats(self):
        statsfile = Path(os.path.join(
            self.__application_args.file_path, str(self._id) + '.stats'))
        try:
            with open(os.path.join(self.__application_args.file_path, str(self._id) + '.stats')) as f:
                data = json.load(f)
                self.set_level(int(data[self._id][0]['level']))
                self.set_poke_stop_visits(int(data[self._id][0]['poke_stop_visits']))
        except IOError:
            logger.warning('[{}] - no Statsfile found', str(self._id))
            self.set_level(0)
            return False
        except json.decoder.JSONDecodeError:
            logger.error('[{}] - Corrupted JSON file found.  Clearing out the file', str(self._id))
            os.remove(statsfile)
            self.set_level(0)
            return False

    def compare_hour(selfs, timestamp):
        if datetime.datetime.fromtimestamp(int(time.time())).strftime('%H') != \
                datetime.datetime.fromtimestamp(int(timestamp)).strftime('%H'):
            return True
        return False

    def stats_collector(self):
        logger.debug2("Creating stats_collector task for {}".format(self._id))
        with self.__mapping_mutex:
            if not self._stats_collector_start:
                if time.time() - self._last_processed_timestamp > 300 or \
                        self.compare_hour(self._last_processed_timestamp):
                    self._last_processed_timestamp = time.time()

                    self.__mitm_mapper_parent.add_stats_to_process(self._id, self.__stats_collected.copy(),
                                                                   self._last_processed_timestamp)
                    self.__stats_collected.clear()
            else:
                self._stats_collector_start = False
                self._last_processed_timestamp = time.time()

    def stats_collect_mon(self, encounter_id: str):
        if not self._generate_stats:
            return
        with self.__mapping_mutex:
            if 106 not in self.__stats_collected:
                self.__stats_collected[106] = {}

            if 'mon' not in self.__stats_collected[106]:
                self.__stats_collected[106]['mon'] = {}

            if 'mon_count' not in self.__stats_collected[106]:
                self.__stats_collected[106]['mon_count'] = 0

            if encounter_id not in self.__stats_collected[106]['mon']:
                self.__stats_collected[106]['mon'][encounter_id] = 1
                self.__stats_collected[106]['mon_count'] += 1
            else:
                self.__stats_collected[106]['mon'][encounter_id] += 1

    def stats_collect_mon_iv(self, encounter_id: str, shiny: int):
        if not self._generate_stats:
            return
        with self.__mapping_mutex:
            if 102 not in self.__stats_collected:
                self.__stats_collected[102] = {}

            if 'mon_iv' not in self.__stats_collected[102]:
                self.__stats_collected[102]['mon_iv'] = {}

            if 'mon_iv_count' not in self.__stats_collected[102]:
                self.__stats_collected[102]['mon_iv_count'] = 0

            if encounter_id not in self.__stats_collected[102]['mon_iv']:
                self.__stats_collected[102]['mon_iv'][encounter_id] = {}
                self.__stats_collected[102]['mon_iv'][encounter_id]['count'] = 1
                self.__stats_collected[102]['mon_iv'][encounter_id]['shiny'] = shiny
                self.__stats_collected[102]['mon_iv_count'] += 1
            else:
                self.__stats_collected[102]['mon_iv'][encounter_id]['count'] += 1

    def stats_collect_raid(self, gym_id: str):
        if not self._generate_stats:
            return
        with self.__mapping_mutex:
            if 106 not in self.__stats_collected:
                self.__stats_collected[106] = {}

            if 'raid' not in self.__stats_collected[106]:
                self.__stats_collected[106]['raid'] = {}

            if 'raid_count' not in self.__stats_collected[106]:
                self.__stats_collected[106]['raid_count'] = 0

            if gym_id not in self.__stats_collected[106]['raid']:
                self.__stats_collected[106]['raid'][gym_id] = 1
                self.__stats_collected[106]['raid_count'] += 1
            else:
                self.__stats_collected[106]['raid'][gym_id] += 1

    def stats_collect_quest(self, stop_id):
        if not self._generate_stats:
            return
        with self.__mapping_mutex:
            if 106 not in self.__stats_collected:
                self.__stats_collected[106] = {}

            if 'quest' not in self.__stats_collected[106]:
                self.__stats_collected[106]['quest'] = {}

            if 'quest_count' not in self.__stats_collected[106]:
                self.__stats_collected[106]['quest_count'] = 0

            if stop_id not in self.__stats_collected[106]['quest']:
                self.__stats_collected[106]['quest'][stop_id] = 1
                self.__stats_collected[106]['quest_count'] += 1
            else:
                self.__stats_collected[106]['quest'][stop_id] += 1

    def stats_collect_location_data(self, location, datarec, start_timestamp, type, rec_timestamp, walker,
                                    transporttype):
        if not self._generate_stats:
            return
        with self.__mapping_mutex:
            if 'location' not in self.__stats_collected:
                self.__stats_collected['location'] = []

            loc_data = (str(self._id),
                        start_timestamp,
                        location.lat,
                        location.lng,
                        rec_timestamp,
                        type,
                        walker,
                        datarec,
                        int(floor(time.time())),
                        transporttype)

            self.__stats_collected['location'].append(loc_data)

            if 'location_count' not in self.__stats_collected:
                self.__stats_collected['location_count'] = 1
                self.__stats_collected['location_ok'] = 0
                self.__stats_collected['location_nok'] = 0
                if datarec:
                    self.__stats_collected['location_ok'] = 1
                else:
                    self.__stats_collected['location_nok'] = 1
            else:
                self.__stats_collected['location_count'] += 1
                if datarec:
                    self.__stats_collected['location_ok'] += 1
                else:
                    self.__stats_collected['location_nok'] += 1

    @staticmethod
    def stats_complete_parser(client_id: int, data, period):
        raid_count = 0
        mon_count = 0
        mon_iv_count = 0
        quest_count = 0

        if 106 in data:
            raid_count = data[106].get('raid_count', 0)
            mon_count = data[106].get('mon_count', 0)
            quest_count = data[106].get('quest_count', 0)

        if 102 in data:
            mon_iv_count = data[102].get('mon_iv_count', 0)
        stats_data = (str(client_id),
                      str(int(period)),
                      str(raid_count),
                      str(mon_count),
                      str(mon_iv_count),
                      str(quest_count)
                      )

        logger.debug('Submit complete stats for {} - Period: {}: {}', str(client_id), str(period),
                     str(stats_data))

        return stats_data

    @staticmethod
    def stats_location_parser(client_id: int, data, period):

        location_count = data.get('location_count', 0)
        location_ok = data.get('location_ok', 0)
        location_nok = data.get('location_nok', 0)

        location_data = (str(client_id),
                         str(int(period)),
                         str(location_count),
                         str(location_ok),
                         str(location_nok))

        logger.debug('Submit location stats for {} - Period: {}: {}', str(client_id), str(period),
                     str(location_data))

        return location_data

    @staticmethod
    def stats_location_raw_parser(client_id: int, data, period):

        data_location_raw = []

        if 'location' in data:
            for loc_raw in data['location']:
                data_location_raw.append(loc_raw)

        logger.debug('Submit raw location stats for {} - Period: {} - Count: {}', str(client_id), str(period),
                     str(len(data_location_raw)))

        return data_location_raw

    @staticmethod
    def stats_detection_raw_parser(client_id: int, data, period):

        data_location_raw = []
        # elf.__stats_collected[106]['mon'][encounter_id]

        if 106 in data:
            if 'mon' in data[106]:
                for mon_id in data[106]['mon']:
                    type_id = str(mon_id)
                    type_count = int(data[106]['mon'][mon_id])

                    data_location_raw.append((str(client_id),
                                              str(type_id),
                                              'mon',
                                              str(type_count),
                                              0,
                                              str(int(period))
                                              ))

            if 'raid' in data[106]:
                for gym_id in data[106]['raid']:
                    type_id = str(gym_id)
                    type_count = int(data[106]['raid'][gym_id])

                    data_location_raw.append((str(client_id),
                                              str(type_id),
                                              'raid',
                                              str(type_count),
                                              0,
                                              str(int(period))
                                              ))

            if 'quest' in data[106]:
                for stop_id in data[106]['quest']:
                    type_id = str(stop_id)
                    type_count = int(data[106]['quest'][stop_id])

                    data_location_raw.append((str(client_id),
                                              str(type_id),
                                              'quest',
                                              str(type_count),
                                              0,
                                              str(int(period))
                                              ))

        if 102 in data:
            if 'mon_iv' in data[102]:
                for mon_id in data[102]['mon_iv']:
                    type_id = str(mon_id)
                    type_count = int(data[102]['mon_iv'][mon_id]['count'])
                    shiny = int(data[102]['mon_iv'][mon_id]["shiny"])

                    data_location_raw.append((str(client_id),
                                              str(type_id),
                                              'mon_iv',
                                              str(type_count),
                                              shiny,
                                              str(int(period))
                                              ))

        logger.debug('Submit raw detection stats for {} - Period: {} - Count: {}', str(client_id),
                     str(period),
                     str(len(data_location_raw)))

        return data_location_raw
