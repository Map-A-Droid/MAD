from datetime import datetime
from typing import List, Tuple

from mapadroid.db.helper.PokemonHelper import PokemonHelper
from mapadroid.db.model import Pokemon
from mapadroid.madmin.endpoints.routes.statistics.AbstractStatistictsRootEndpoint import AbstractStatisticsRootEndpoint
from mapadroid.utils.gamemechanicutil import calculate_mon_level, calculate_iv
from mapadroid.utils.language import get_mon_name


class GameStatsMonEndpoint(AbstractStatisticsRootEndpoint):
    """
    "/get_game_stats_mon"
    """

    # TODO: Auth
    async def get(self):
        minutes_usage = self._get_minutes_usage_query_args()
        # Spawn
        iv = []
        noniv = []
        sumg = []
        sumup = {}

        data: List[Tuple[int, int, int]] = await PokemonHelper.get_pokemon_count(self._session, minutes_usage)
        for dat in data:
            if dat[2] == 1:
                iv.append([dat[0], dat[1]])
            else:
                noniv.append([dat[0], dat[1]])

            if dat[0] in sumup:
                sumup[dat[0]] += dat[1]
            else:
                sumup[dat[0]] = dat[1]

        for dat in sumup:
            sumg.append([dat, sumup[dat]])

        spawn = {'iv': iv, 'noniv': noniv, 'sum': sumg}

        # good_spawns avg
        good_spawns = []
        best_mon_spawns: List[Pokemon] = await PokemonHelper.get_best_pokemon_spawns(self._session)
        if best_mon_spawns:
            for mon in best_mon_spawns:
                mon_img = self._generate_mon_icon_url(mon.pokemon_id, mon.form, mon.costume)
                mon_name = await get_mon_name(mon.pokemon_id)
                lvl = calculate_mon_level(mon.cp_multiplier)

                good_spawns.append({'id': mon.pokemon_id, 'iv': round(calculate_iv(mon.individual_attack,
                                                                                   mon.individual_defense,
                                                                                   mon.individual_stamina),
                                                                      0),
                                    'lvl': lvl, 'cp': mon.cp, 'img': mon_img,
                                    'name': mon_name,
                                    'periode': datetime.fromtimestamp(mon.last_modified.timestamp())
                                   .strftime(self._datetimeformat)})
        stats = {'spawn': spawn, 'good_spawns': good_spawns}
        return await self._json_response(stats)
