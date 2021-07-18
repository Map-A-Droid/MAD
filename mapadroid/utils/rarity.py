import asyncio
from asyncio import Task
from timeit import default_timer
from typing import Optional

from mapadroid.db.helper.PokemonHelper import PokemonHelper
from mapadroid.utils.logging import LoggerEnums, get_logger

logger = get_logger(LoggerEnums.utils)


class Rarity(object):
    def __init__(self, args, dbwrapper):
        self.args = args
        self._dbwrapper = dbwrapper
        self._rarity = {}
        self.rarity_updater_task: Optional[Task] = None

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

    async def start_dynamic_rarity(self):
        loop = asyncio.get_running_loop()
        self.rarity_updater_task = loop.create_task(self.dynamic_rarity_refresher())

    async def dynamic_rarity_refresher(self):

        hours = self.args.rarity_hours
        update_frequency_mins = self.args.rarity_update_frequency
        refresh_time_sec = update_frequency_mins * 60

        while True:
            logger.info('Updating dynamic rarity...')

            start = default_timer()
            async with self._dbwrapper as session, session:
                db_rarities = await PokemonHelper.get_pokemon_spawn_counts(session, hours)
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
            await asyncio.sleep(refresh_time_sec)

    def rarity_by_id(self, pokemonid):
        if pokemonid in self._rarity:
            return self._rarity[pokemonid]
        else:
            return 0
