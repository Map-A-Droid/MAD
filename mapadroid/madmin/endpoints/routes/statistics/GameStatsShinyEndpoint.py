from datetime import datetime
from typing import List, Optional, Tuple, Dict

from loguru import logger

from mapadroid.db.helper.PokemonHelper import PokemonHelper
from mapadroid.db.model import Pokemon, TrsStatsDetectMonRaw
from mapadroid.madmin.endpoints.routes.statistics.AbstractStatistictsRootEndpoint import AbstractStatisticsRootEndpoint
from mapadroid.utils.language import get_mon_name


class GameStatsShinyEndpoint(AbstractStatisticsRootEndpoint):
    """
    "/get_game_stats_shiny"
    """

    # TODO: Auth
    async def get(self):
        logger.debug2('game_stats_shiny_v2')
        timestamp_from: Optional[int] = self._request.query.get("from")
        if timestamp_from:
            timestamp_from = self._local2utc(int(timestamp_from))
            logger.debug2('using timestamp_from: {}', timestamp_from)
        timestamp_to: Optional[int] = self._request.query.get("to")
        if timestamp_to:
            timestamp_to = self._local2utc(int(timestamp_to))
            logger.debug2('using timestamp_from: {}', timestamp_to)

        tmp_perworker_v2 = {}
        data: Dict[int, Tuple[Pokemon, List[TrsStatsDetectMonRaw]]] = await PokemonHelper \
            .get_all_shiny(self._session, timestamp_from, timestamp_to)
        found_shiny_mon_id = []
        shiny_count: Dict[int, Dict] = {}
        mon_names = {}
        tmp_perhour_v2 = {}

        if data is None or len(data) == 0:
            # Whyyyyy....
            return await self._json_response({'empty': True})

        shiny_stats_v2 = []
        for encounter_id, (mon, stats) in data.items():
            mon_img = self._generate_mon_icon_url(mon.pokemon_id, mon.form)
            mon_name = await get_mon_name(mon.pokemon_id)
            mon_names[mon.pokemon_id] = mon_name
            found_shiny_mon_id.append(
                mon.pokemon_id)  # append everything now, we will set() it later to remove duplicates
            if mon.pokemon_id not in shiny_count:
                shiny_count[mon.pokemon_id] = {}
            if mon.form not in shiny_count[mon.pokemon_id]:
                shiny_count[mon.pokemon_id][mon.form] = 0
            shiny_count[mon.pokemon_id][mon.form] += 1

            for stat in stats:
                if stat.worker not in tmp_perworker_v2:
                    tmp_perworker_v2[stat.worker] = 0
                tmp_perworker_v2[stat.worker] += 1
                # there is later strftime which converts to local time too, can't use utc2local - it will do double shift
                timestamp = datetime.fromtimestamp(stat.timestamp_scan)

                # TODO: This can trigger too often...
                if timestamp.hour in tmp_perhour_v2:
                    tmp_perhour_v2[timestamp.hour] += 1
                else:
                    tmp_perhour_v2[timestamp.hour] = 1

                shiny_stats_v2.append({'img': mon_img, 'name': mon_name, 'worker': stat.worker, 'lat': mon.latitude,
                                       'lat_5': "{:.5f}".format(mon.latitude), 'lng_5': "{:.5f}".format(mon.longitude),
                                       'lng': mon.longitude, 'timestamp': timestamp.strftime(self._datetimeformat),
                                       'form': mon.form, 'mon_id': mon.pokemon_id, 'encounter_id': str(encounter_id)})

        global_shiny_stats_v2 = []
        global_shiny_stats: List[Tuple[int, int, int, int, int]] = await PokemonHelper \
            .get_count_iv_scanned_of_mon_ids(self._session, set(found_shiny_mon_id),
                                             timestamp_from, timestamp_to)
        for count, mon_id, form, gender, costume in global_shiny_stats:
            if mon_id in shiny_count and form in shiny_count[mon_id]:
                odds = round(count / shiny_count[mon_id][form], 0)
                mon_img = self._generate_mon_icon_url(mon_id, form)
                global_shiny_stats_v2.append({'name': mon_names[mon_id], 'count': count, 'img': mon_img,
                                              'shiny': shiny_count[mon_id][form], 'odds': odds,
                                              'mon_id': mon_id, 'form': form, 'gender': gender,
                                              'costume': costume})

        shiny_stats_perworker_v2 = []
        for worker in tmp_perworker_v2:
            shiny_stats_perworker_v2.append({'name': worker, 'count': tmp_perworker_v2[worker]})

        shiny_stats_perhour_v2 = []
        for hour in tmp_perhour_v2:
            shiny_stats_perhour_v2.append([hour, tmp_perhour_v2[hour]])

        stats = {'empty': False, 'shiny_statistics': shiny_stats_v2,
                 'global_shiny_statistics': global_shiny_stats_v2, 'per_worker': shiny_stats_perworker_v2,
                 'per_hour': shiny_stats_perhour_v2}
        return await self._json_response(stats)
