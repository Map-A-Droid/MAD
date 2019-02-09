import json
import logging
import os
import sys
from pathlib import Path

log = logging.getLogger(__name__)


class PlayerStats(object):
    def __init__(self, id):
        self._id = id
        self._level = 0

    def set_level(self, level):
        log.info('[%s] - set level %s' % (str(self._id), str(level)))
        self._level = int(level)
        return True

    def get_level(self):
        return self._level

    def _gen_player_stats(self, data):
        if 'inventory_delta' not in data:
            log.debug('{{gen_player_stats}} cannot generate new stats')
            return True
        stats = data['inventory_delta'].get("inventory_items", None)
        if len(stats) > 0:
            for data_inventory in stats:
                player_level = data_inventory['inventory_item_data']['player_stats']['level']
                if int(player_level) > 0:
                    log.debug('{{gen_player_stats}} saving new playerstats')
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
                    with open(self._id + '.stats', 'w') as outfile:
                        json.dump(data, outfile, indent=4, sort_keys=True)

    def _open_player_stats(self):
        statsfile = Path(str(self._id) + '.stats')
        if not statsfile.is_file():
            log.error('[%s] - no Statsfile found' % (str(self._id)))
            self.set_level(0)
            return False

        with open(str(self._id) + '.stats') as f:
            data = json.load(f)

        self.set_level(data[self._id][0]['level'])
