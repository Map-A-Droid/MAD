import logging
import os, sys
from pathlib import Path
import json

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
        stats= data['inventory_delta'].get("inventory_items", None)
        if len(stats) > 0 :
            for data_inventory in stats:
                player_level = data_inventory['inventory_item_data']['player_stats']['level']
                if int(player_level) > 0:
                    
                    if os.path.exists('status.json'):
                        with open('status.json') as f:
                            data = json.load(f)
                    else:
                        data = {}
                    
                    log.debug('{{gen_player_stats}} saving new playerstats')
                    self.set_level(int(player_level))
                            
                    data[self._id]['player'] = {  
                        'level': str(data_inventory['inventory_item_data']['player_stats']['level']), 
                        'experience': str(data_inventory['inventory_item_data']['player_stats']['experience']),
                        'km_walked': str(data_inventory['inventory_item_data']['player_stats']['km_walked']),
                        'pokemons_encountered': str(data_inventory['inventory_item_data']['player_stats']['pokemons_encountered']),
                        'poke_stop_visits': str(data_inventory['inventory_item_data']['player_stats']['poke_stop_visits'])
                    }
                    with open('status.json', 'w') as outfile:  
                        json.dump(data, outfile, indent=4, sort_keys=True)
                        
    def _open_player_stats(self):
        statsfile = Path('status.json')
        if not statsfile.is_file():
            log.error('[%s] - no Statsfile found' % (str(self._id)))
            self.set_level(0)
            return False
            
        with open('status.json') as f:
            data = json.load(f)
            
        if self._id in data:
            if 'player' in data[self._id]:
                self.set_level(data[self._id]['player']['level'])
            else:
                self.set_level(0)
        else:
            self.set_level(0)