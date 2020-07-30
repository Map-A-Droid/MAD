import time
from threading import Thread
from timeit import default_timer
from mapadroid.utils.logging import get_logger, LoggerEnums


logger = get_logger(LoggerEnums.utils)


class Rarity(object):
    def __init__(self, args, dbwrapper):
        self.args = args
        self._dbwrapper = dbwrapper
        self._rarity = {}

    def get_pokemon_rarity(self, total_spawns_all, total_spawns_pokemon):
        spawn_group = 1

        spawn_rate_pct = total_spawns_pokemon / float(total_spawns_all)
        spawn_rate_pct = round(100 * spawn_rate_pct, 4)

        if spawn_rate_pct == 0:
            spawn_group = 0
        elif spawn_rate_pct < 0.01:
            spawn_group = 5
        elif spawn_rate_pct < 0.03:
            spawn_group = 4
        elif spawn_rate_pct < 0.5:
            spawn_group = 3
        elif spawn_rate_pct < 1:
            spawn_group = 2

        return spawn_group

    def start_dynamic_rarity(self):

        rarity_thread = Thread(name='system', target=self.dynamic_rarity_refresher)
        rarity_thread.daemon = True
        rarity_thread.start()

    def dynamic_rarity_refresher(self):

        hours = self.args.rarity_hours
        update_frequency_mins = self.args.rarity_update_frequency
        refresh_time_sec = update_frequency_mins * 60

        while True:
            logger.info('Updating dynamic rarity...')

            start = default_timer()
            db_rarities = self._dbwrapper.get_pokemon_spawns(hours)
            logger.debug('Pokemon Rarity: {}', db_rarities)
            total = db_rarities['total']
            pokemon = db_rarities['pokemon']

            # Store as an easy lookup table for front-end.

            for poke in pokemon:
                self._rarity[poke[0]] = self.get_pokemon_rarity(
                    total, int(poke[1]))

            duration = default_timer() - start
            logger.info('Updated dynamic rarity. It took {}s for {} entries.', round(duration, 2), total)
            logger.debug('Waiting {} minutes before next dynamic rarity update.', refresh_time_sec / 60)
            time.sleep(refresh_time_sec)

    def rarity_by_id(self, pokemonid):
        if pokemonid in self._rarity:
            return self._rarity[pokemonid]
        else:
            return 0
