import logging
import time
from timeit import default_timer
from threading import Thread

log = logging.getLogger(__name__)


class Rarity(object):
    def __init__(self, args):
        self.args = args
        self._dbwrapper = None
        self._rarity = {}

    def get_pokemon_rarity(self, total_spawns_all, total_spawns_pokemon):
        spawn_group = 'Common'

        spawn_rate_pct = total_spawns_pokemon / float(total_spawns_all)
        spawn_rate_pct = round(100 * spawn_rate_pct, 4)

        if spawn_rate_pct == 0:
            spawn_group = 'New Spawn'
        elif spawn_rate_pct < 0.01:
            spawn_group = 'Ultra Rare'
        elif spawn_rate_pct < 0.03:
            spawn_group = 'Very Rare'
        elif spawn_rate_pct < 0.5:
            spawn_group = 'Rare'
        elif spawn_rate_pct < 1:
            spawn_group = 'Uncommon'

        return spawn_group

    def start_dynamic_rarity(self, dbwrapper):
        self._dbwrapper = dbwrapper
        t = Thread(target=self.dynamic_rarity_refresher,
                   name='dynamic_rarity')
        t.daemon = False
        t.start()

    def dynamic_rarity_refresher(self):

        hours = self.args.rarity_hours
        update_frequency_mins = self.args.rarity_update_frequency
        refresh_time_sec = update_frequency_mins * 60

        while True:
            log.info('Updating dynamic rarity...')

            start = default_timer()
            db_rarities = self._dbwrapper.get_pokemon_spawns(hours)
            log.debug('Pokemon Rarity: %s' % (str(db_rarities)))
            total = db_rarities['total']
            pokemon = db_rarities['pokemon']

            # Store as an easy lookup table for front-end.

            for poke in pokemon:
                self._rarity[poke[0]] = self.get_pokemon_rarity(total, int(poke[1]))

            duration = default_timer() - start
            log.info('Updated dynamic rarity. It took %.2fs for %d entries.',
                     duration,
                     total)

            log.debug('Waiting %d minutes before next dynamic rarity update.',
                      refresh_time_sec / 60)
            time.sleep(refresh_time_sec)

    def rarity_by_id(self, pokemonid):
        if pokemonid in self._rarity:
            return self._rarity[pokemonid]
        else:
            return "New Spawn"
