import json
import os
from pathlib import Path
import time
from threading import Lock, Thread

from utils.logging import logger
from utils.walkerArgs import parseArgs
from utils.functions import get_min_period, get_now_timestamp

args = parseArgs()


class PlayerStats(object):
    def __init__(self, id, db_wrapper):
        self._id = id
        self._level = 0
        self._last_action_time = 0
        self._last_period = 0
        self._stats_collect = {}
        self._stats_collector_start = True
        self._last_processed_timestamp = 0
        self._db_wrapper = db_wrapper
        self._stats_period = 0
        self.__mapping_mutex = Lock()
        t_usage = Thread(name='stats_processor',
                         target=self.stats_processor)
        t_usage.daemon = False
        t_usage.start()

    def set_level(self, level):
        logger.info('[{}] - set level {}', str(self._id), str(level))
        self._level = int(level)
        return True

    def get_level(self):
        return self._level

    def gen_player_stats(self, data):
        if 'inventory_delta' not in data:
            logger.debug('gen_player_stats cannot generate new stats')
            return True
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
                    with open(os.path.join(args.file_path, str(self._id) + '.stats'), 'w') as outfile:
                        json.dump(data, outfile, indent=4, sort_keys=True)

    def open_player_stats(self):
        statsfile = Path(os.path.join(
            args.file_path, str(self._id) + '.stats'))
        if not statsfile.is_file():
            logger.error('[{}] - no Statsfile found', str(self._id))
            self.set_level(0)
            return False

        with open(os.path.join(args.file_path, str(self._id) + '.stats')) as f:
            data = json.load(f)

        self.set_level(data[self._id][0]['level'])

    def stats_processor(self):
        while True:
            self.__mapping_mutex.acquire()
            if self._stats_collector_start is False:
                for save_ts in self._stats_collect.copy():
                    if int(save_ts) < int(self._last_processed_timestamp):
                        collect_data = self._stats_collect.get(save_ts, []).copy()
                        self.stats_complete_parser(collect_data, save_ts)
                        logger.error(int(self._last_processed_timestamp)-int(save_ts))
                        if int(self._last_processed_timestamp)-int(save_ts) > 10:
                            print ('TURE')
                            del self._stats_collect[save_ts]

                self._last_processed_timestamp = int(time.time())

            self.__mapping_mutex.release()
            time.sleep(5)

    def stats_collector(self, prototyp):
        self.__mapping_mutex.acquire()
        self._stats_period = get_min_period()
        period = self._stats_period

        if self._stats_collector_start:
            self._stats_collector_start = False
            self._last_processed_timestamp = int(time.time())

        if period not in self._stats_collect:
            self._stats_collect[period] = {}

        if prototyp not in self._stats_collect[period]:
            self._stats_collect[period][prototyp] = {}
            self._stats_collect[period][prototyp]['protocount'] = 1
        else:
            print (self._stats_collect[period])
            self._stats_collect[period][prototyp]['protocount'] += 1
        self.__mapping_mutex.release()

    def stats_collect_mon(self, encounter_id):
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

    def stats_collect_mon_iv(self, encounter_id):
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

    def stats_collect_raid(self, gym_id):
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

    def stats_collect_location_data(self, location, datarec, start_timestamp, typ, rec_timestamp):
        period = self._stats_period
        now = start_timestamp
        if period not in self._stats_collect:
            self._stats_collect[period] = {}
        if 'location' not in self._stats_collect[period]:
            self._stats_collect[period]['location'] = {}

        if now not in self._stats_collect[period]['location']:
            self._stats_collect[period]['location'][now] = {}

        self._stats_collect[period]['location'][now]['lat'] = location.lat
        self._stats_collect[period]['location'][now]['lng'] = location.lng
        self._stats_collect[period]['location'][now]['datarec'] = datarec
        self._stats_collect[period]['location'][now]['typ'] = typ
        self._stats_collect[period]['location'][now]['timestamp_start'] = rec_timestamp

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

        if 106 in data:
            raid_count = data[106].get('raid_count', 0)
            mon_count = data[106].get('mon_count', 0)

        if 102 in data:
            mon_iv_count = data[102].get('mon_iv_count', 0)
        stats_data = (str(self._id), str(int(period)), str(raid_count), str(mon_count), str(mon_iv_count))
        logger.info('Submit complete stats for {} - Period: {}: {}', str(self._id), str(period), str(stats_data))

        self._db_wrapper.submit_stats_complete(self._id, period, stats_data)









