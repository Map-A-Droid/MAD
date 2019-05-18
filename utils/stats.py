import json
import os
from multiprocessing import Lock
from pathlib import Path

from db.dbWrapperBase import DbWrapperBase
from utils.logging import logger
from utils.functions import get_min_period


class PlayerStats(object):
    def __init__(self, id, application_args, db_wrapper: DbWrapperBase):
        self._id = id
        self.__application_args = application_args
        self._level = 0
        self._last_action_time = 0
        self._last_period = 0
        self._stats_collect = {}
        self._stats_collector_start = True
        self._last_processed_timestamp = 0
        self._db_wrapper: DbWrapperBase = db_wrapper
        self._stats_period = 0
        self.__mapping_mutex = Lock()

    def set_level(self, level):
        logger.debug('[{}] - set level {}', str(self._id), str(level))
        self._level = int(level)
        return True

    def get_level(self):
        return self._level

    def gen_player_stats(self, data: dict):
        if 'inventory_delta' not in data:
            logger.debug('gen_player_stats cannot generate new stats')
            return
        stats = data['inventory_delta'].get("inventory_items", None)
        if len(stats) > 0:
            for data_inventory in stats:
                player_level = data_inventory['inventory_item_data']['player_stats']['level']
                if int(player_level) > 0:
                    logger.debug('{{gen_player_stats}} saving new playerstats')
                    self.set_level(int(player_level))

                    data = {}
                    data[self._id] = []
                    data[self._id].append({
                        'level': str(data_inventory['inventory_item_data']['player_stats']['level']),
                        'experience': str(data_inventory['inventory_item_data']['player_stats']['experience']),
                        'km_walked': str(data_inventory['inventory_item_data']['player_stats']['km_walked']),
                        'pokemons_encountered': str(data_inventory['inventory_item_data']['player_stats']['pokemons_encountered']),
                        'poke_stop_visits': str(data_inventory['inventory_item_data']['player_stats']['poke_stop_visits'])
                    })
                    with open(os.path.join(self.__application_args.file_path, str(self._id) + '.stats'), 'w') as outfile:
                        json.dump(data, outfile, indent=4, sort_keys=True)

    def open_player_stats(self):
        statsfile = Path(os.path.join(
            self.__application_args.file_path, str(self._id) + '.stats'))
        if not statsfile.is_file():
            logger.error('[{}] - no Statsfile found', str(self._id))
            self.set_level(0)
            return False

        with open(os.path.join(self.__application_args.file_path, str(self._id) + '.stats')) as f:
            data = json.load(f)

        self.set_level(data[self._id][0]['level'])

    def stats_collector(self):
        self.__mapping_mutex.acquire()
        data_send_stats = []
        data_send_location = []
        self._stats_period = get_min_period()
        period = self._stats_period

        if not self._stats_collector_start:
            if self._last_processed_timestamp != period:

                collect_data = self._stats_collect.get(self._last_processed_timestamp, [])

                data_send_stats.append(self.stats_complete_parser(collect_data, self._last_processed_timestamp))
                data_send_location.append(self.stats_location_parser(collect_data, self._last_processed_timestamp))
                data_send_location_raw = self.stats_location_raw_parser(collect_data, self._last_processed_timestamp)
                data_send_detection_raw = self.stats_detection_raw_parser(collect_data, self._last_processed_timestamp)

                self._stats_collect[self._last_processed_timestamp] = None
                del self._stats_collect[self._last_processed_timestamp]

                self._db_wrapper.submit_stats_complete(data_send_stats)
                self._db_wrapper.submit_stats_locations(data_send_location)
                self._db_wrapper.submit_stats_locations_raw(data_send_location_raw)
                self._db_wrapper.submit_stats_detections_raw(data_send_detection_raw)
                self._db_wrapper.cleanup_statistics()
                self._last_processed_timestamp = period

        if self._stats_collector_start:
            self._stats_collector_start = False
            self._last_processed_timestamp = period

        if period not in self._stats_collect:
            self._stats_collect[period] = {}

        self.__mapping_mutex.release()

    def stats_collect_mon(self, encounter_id: str):
        period = self._stats_period

        if period not in self._stats_collect:
            self._stats_collect[period] = {}

        if 106 not in self._stats_collect[period]:
            self._stats_collect[period][106] = {}

        if 'mon' not in self._stats_collect[period][106]:
            self._stats_collect[period][106]['mon'] = {}

        if 'mon_count' not in self._stats_collect[period][106]:
            self._stats_collect[period][106]['mon_count'] = 0

        if encounter_id not in self._stats_collect[period][106]['mon']:
            self._stats_collect[period][106]['mon'][encounter_id] = 1
            self._stats_collect[period][106]['mon_count'] += 1
        else:
            self._stats_collect[period][106]['mon'][encounter_id] += 1

    def stats_collect_mon_iv(self, encounter_id: str):
        period = self._stats_period

        if period not in self._stats_collect:
            self._stats_collect[period] = {}

        if 102 not in self._stats_collect[period]:
            self._stats_collect[period][102] = {}

        if 'mon_iv' not in self._stats_collect[period][102]:
            self._stats_collect[period][102]['mon_iv'] = {}

        if 'mon_iv_count' not in self._stats_collect[period][102]:
            self._stats_collect[period][102]['mon_iv_count'] = 0

        if encounter_id not in self._stats_collect[period][102]['mon_iv']:
            self._stats_collect[period][102]['mon_iv'][encounter_id] = 1
            self._stats_collect[period][102]['mon_iv_count'] += 1
        else:
            self._stats_collect[period][102]['mon_iv'][encounter_id] += 1

    def stats_collect_raid(self, gym_id: str):
        period = self._stats_period

        if period not in self._stats_collect:
            self._stats_collect[period] = {}

        if 106 not in self._stats_collect[period]:
            self._stats_collect[period][106] = {}

        if 'raid' not in self._stats_collect[period][106]:
            self._stats_collect[period][106]['raid'] = {}

        if 'raid_count' not in self._stats_collect[period][106]:
            self._stats_collect[period][106]['raid_count'] = 0

        if gym_id not in self._stats_collect[period][106]['raid']:
            self._stats_collect[period][106]['raid'][gym_id] = 1
            self._stats_collect[period][106]['raid_count'] += 1
        else:
            self._stats_collect[period][106]['raid'][gym_id] += 1

    def stats_collect_quest(self, stop_id):
        period = self._stats_period

        if period not in self._stats_collect:
            self._stats_collect[period] = {}

        if 106 not in self._stats_collect[period]:
            self._stats_collect[period][106] = {}

        if 'quest' not in self._stats_collect[period][106]:
            self._stats_collect[period][106]['quest'] = {}

        if 'quest_count' not in self._stats_collect[period][106]:
            self._stats_collect[period][106]['quest_count'] = 0

        if stop_id not in self._stats_collect[period][106]['quest']:
            self._stats_collect[period][106]['quest'][stop_id] = 1
            self._stats_collect[period][106]['quest_count'] += 1
        else:
            self._stats_collect[period][106]['quest'][stop_id] += 1

    def stats_collect_location_data(self, location, datarec, start_timestamp, type, rec_timestamp, walker,
                                    transporttype):
        period = self._stats_period
        if period not in self._stats_collect:
            self._stats_collect[period] = {}
        if 'location' not in self._stats_collect[period]:
            self._stats_collect[period]['location'] = []

        loc_data = (str(self._id),
                    start_timestamp,
                    location.lat,
                    location.lng,
                    rec_timestamp,
                    type,
                    walker,
                    datarec,
                    period,
                    transporttype)

        self._stats_collect[period]['location'].append(loc_data)

        if 'location_count' not in self._stats_collect[period]:
            self._stats_collect[period]['location_count'] = 1
            self._stats_collect[period]['location_ok'] = 0
            self._stats_collect[period]['location_nok'] = 0
            if datarec:
                self._stats_collect[period]['location_ok'] = 1
            else:
                self._stats_collect[period]['location_nok'] = 1
        else:
            self._stats_collect[period]['location_count'] += 1
            if datarec:
                self._stats_collect[period]['location_ok'] += 1
            else:
                self._stats_collect[period]['location_nok'] += 1

    def stats_complete_parser(self, data, period):
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
        stats_data = (str(self._id),
                      str(int(period)),
                      str(raid_count),
                      str(mon_count),
                      str(mon_iv_count),
                      str(quest_count)
                      )

        logger.debug('Submit complete stats for {} - Period: {}: {}', str(self._id), str(period), str(stats_data))

        return stats_data

    def stats_location_parser(self, data, period):

        location_count = data.get('location_count', 0)
        location_ok = data.get('location_ok', 0)
        location_nok = data.get('location_nok', 0)

        location_data = (str(self._id),
                         str(int(period)),
                         str(location_count),
                         str(location_ok),
                         str(location_nok))

        logger.debug('Submit location stats for {} - Period: {}: {}', str(self._id), str(period), str(location_data))

        return location_data

    def stats_location_raw_parser(self, data, period):

        data_location_raw = []

        if 'location' in data:
            for loc_raw in data['location']:
                data_location_raw.append(loc_raw)

        logger.debug('Submit raw location stats for {} - Period: {} - Count: {}', str(self._id), str(period),
                    str(len(data_location_raw)))

        return data_location_raw

    def stats_detection_raw_parser(self, data, period):

        data_location_raw = []
        # elf._stats_collect[period][106]['mon'][encounter_id]

        if 106 in data:
            if 'mon' in data[106]:
                for mon_id in data[106]['mon']:
                    type_id = str(mon_id)
                    type_count = int(data[106]['mon'][mon_id])

                    data_location_raw.append((str(self._id),
                                             str(type_id),
                                             'mon',
                                             str(type_count),
                                             str(int(period))
                                              ))

            if 'raid' in data[106]:
                for gym_id in data[106]['raid']:
                    type_id = str(gym_id)
                    type_count = int(data[106]['raid'][gym_id])

                    data_location_raw.append((str(self._id),
                                             str(type_id),
                                             'raid',
                                             str(type_count),
                                             str(int(period))
                                              ))

            if 'quest' in data[106]:
                for stop_id in data[106]['quest']:
                    type_id = str(stop_id)
                    type_count = int(data[106]['quest'][stop_id])

                    data_location_raw.append((str(self._id),
                                             str(type_id),
                                             'quest',
                                             str(type_count),
                                             str(int(period))
                                              ))

        if 102 in data:
            if 'mon_iv' in data[102]:
                for mon_id in data[102]['mon_iv']:
                    type_id = str(mon_id)
                    type_count = int(data[102]['mon_iv'][mon_id])

                    data_location_raw.append((str(self._id),
                                             str(type_id),
                                             'mon_iv',
                                             str(type_count),
                                             str(int(period))
                                              ))

        logger.debug('Submit raw detection stats for {} - Period: {} - Count: {}', str(self._id), str(period),
                    str(len(data_location_raw)))

        return data_location_raw












