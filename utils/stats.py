import logging
import os, sys
from pathlib import Path
import json

log = logging.getLogger(__name__)

class PlayerStats(object):
    def __init__(self, id, name):
        self._id = id
        self._level = 0
        self._name = name

    def set_level(self, level):
        log.info('[%s] - set level %s' % (str(self._id), str(level)))
        self._level = int(level)
        return True
		
    def set_name(self, name):
        log.info('[%s] - set name %s' % (str(self._id), str(name)))
        self._name = str(name)
        return True
        
    def get_level(self):
        return self._level
		
    def get_name(self):
        return self._name
            
    def _gen_player_stats(self, data):
        if 'inventory_delta' not in data:
            log.debug('{{gen_player_stats}} cannot generate new stats')
            return True
        stats= data['inventory_delta'].get("inventory_items", None)
        if len(stats) > 0 :
            for data_inventory in stats:
                player_level = data_inventory['inventory_item_data']['player_stats']['level']
                player_name = data_inventory['inventory_item_data']['player_public_profile']['name']
				#or
				#player_name = data_inventory['inventory_item_data']['player_data ']['username']

                if int(player_level) > 0:
                    log.debug('{{gen_player_stats}} saving new playerstats')
                    self.set_level(int(player_level))
					#self.set_name(str(player_name))
                    self.set_name(int(player_name))
                            
                    data = {}  
                    data[self._id] = []
                    data[self._id].append({  
                        'name': str(data_inventory['inventory_item_data']['player_stats']['name']),
                        'level': str(data_inventory['inventory_item_data']['player_stats']['level']),
                        'experience': str(data_inventory['inventory_item_data']['player_stats']['experience']),
                        'prev_level_xp': str(data_inventory['inventory_item_data']['player_stats']['prev_level_xp']),
                        'next_level_xp': str(data_inventory['inventory_item_data']['player_stats']['next_level_xp']),
                        'km_walked': str(data_inventory['inventory_item_data']['player_stats']['km_walked']),
                        'pokemons_encountered': str(data_inventory['inventory_item_data']['player_stats']['pokemons_encountered']),
                        'pokemons_captured': str(data_inventory['inventory_item_data']['player_stats']['pokemons_captured']),
                        'poke_stop_visits': str(data_inventory['inventory_item_data']['player_stats']['poke_stop_visits']),
                        'unique_pokedex_entries': str(data_inventory['inventory_item_data']['player_stats']['unique_pokedex_entries']),
                        'evolutions': str(data_inventory['inventory_item_data']['player_stats']['evolutions']),
                        'pokeballs_thrown': str(data_inventory['inventory_item_data']['player_stats']['pokeballs_thrown']),
                        'eggs_hatched': str(data_inventory['inventory_item_data']['player_stats']['eggs_hatched']),
                        'big_magikarp_caught': str(data_inventory['inventory_item_data']['player_stats']['big_magikarp_caught']),
                        'battle_attack_won': str(data_inventory['inventory_item_data']['player_stats']['battle_attack_won']),
                        'battle_attack_total': str(data_inventory['inventory_item_data']['player_stats']['battle_attack_total']),
                        'battle_defended_won': str(data_inventory['inventory_item_data']['player_stats']['battle_defended_won']),
                        'battle_training_won': str(data_inventory['inventory_item_data']['player_stats']['battle_training_won']),
                        'battle_training_total': str(data_inventory['inventory_item_data']['player_stats']['battle_training_total']),
                        'prestige_raised_total': str(data_inventory['inventory_item_data']['player_stats']['prestige_raised_total']),
                        'prestige_dropped_total': str(data_inventory['inventory_item_data']['player_stats']['prestige_dropped_total']),
                        'pokemon_deployed': str(data_inventory['inventory_item_data']['player_stats']['pokemon_deployed']),
                        'small_rattata_caught': str(data_inventory['inventory_item_data']['player_stats']['small_rattata_caught']),
                        'num_raid_battle_won': str(data_inventory['inventory_item_data']['player_stats']['num_raid_battle_won']),
                        'num_raid_battle_total': str(data_inventory['inventory_item_data']['player_stats']['num_raid_battle_total']),
                        'num_legendary_battle_won': str(data_inventory['inventory_item_data']['player_stats']['num_legendary_battle_won']),
                        'num_legendary_battle_total': str(data_inventory['inventory_item_data']['player_stats']['num_legendary_battle_total']),
                        'num_berries_fed': str(data_inventory['inventory_item_data']['player_stats']['num_berries_fed']),
                        'total_defended_ms': str(data_inventory['inventory_item_data']['player_stats']['total_defended_ms']),
                        'num_challenge_quests_completed': str(data_inventory['inventory_item_data']['player_stats']['num_challenge_quests_completed']),
                        'num_trades': str(data_inventory['inventory_item_data']['player_stats']['num_trades']),
                        'num_max_level_friends': str(data_inventory['inventory_item_data']['player_stats']['num_max_level_friends'])
                    })
                    with open(self._id + '.stats', 'w') as outfile:  
                        json.dump(data, outfile, indent=4, sort_keys=True)
                        
    def _open_player_stats(self):
        statsfile = Path(str(self._id) + '.stats')
        if not statsfile.is_file():
            log.error('[%s] - no Statsfile found' % (str(self._id)))
            self.set_level(0)
			#self.set_name("")
            self.set_name(0)
            return False
            
        with open(str(self._id) + '.stats') as f:
            data = json.load(f)
            
        self.set_level(data[self._id][0]['level'])
		#self.set_name(data[self._name][""]['name'])
        self.set_name(data[self._name][0]['name'])