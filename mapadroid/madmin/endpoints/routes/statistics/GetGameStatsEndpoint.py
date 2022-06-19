from typing import List, Optional, Tuple, Dict

from mapadroid.db.helper.GymHelper import GymHelper
from mapadroid.db.helper.TrsStatsDetectHelper import TrsStatsDetectHelper
from mapadroid.db.helper.TrsStatsLocationHelper import TrsStatsLocationHelper
from mapadroid.db.helper.TrsStatsLocationRawHelper import TrsStatsLocationRawHelper
from mapadroid.db.helper.TrsUsageHelper import TrsUsageHelper
from mapadroid.db.model import TrsUsage
from mapadroid.madmin.endpoints.routes.statistics.AbstractStatistictsRootEndpoint import AbstractStatisticsRootEndpoint
from mapadroid.utils.collections import Location
from mapadroid.utils.madGlobals import TeamColours


class GetGameStatsEndpoint(AbstractStatisticsRootEndpoint):
    """
    "/get_game_stats"
    """

    # TODO: Auth
    async def get(self):
        minutes_usage: Optional[int] = self._get_minutes_usage_query_args()

        # statistics_get_detection_count
        stats_detect: Dict[
            str, Dict[int, Tuple[int, int, int, int]]] = await TrsStatsDetectHelper.get_detection_count_per_worker(
            self._session, hourly=False)
        detection = []
        for worker, mapped_data in stats_detect.items():
            for hour_timestamp, values in mapped_data.items():
                sum_mons, sum_iv, sum_raids, sum_quests = values
                detection.append({'worker': str(worker),
                                  'mons': str(sum_mons),
                                  'mons_iv': str(sum_iv),
                                  'raids': str(sum_raids),
                                  'quests': str(sum_quests)})

        stats_location: Dict[str, Tuple[int, int, int, float]] = await TrsStatsLocationHelper.get_location_info(
            self._session)
        location_info = []
        for worker, mapped_data in stats_location.items():
            location_count, location_ok, location_nok, failure_rate = mapped_data
            location_info.append({'worker': str(worker),
                                  'locations': str(location_count),
                                  'locationsok': str(location_ok),
                                  'locationsnok': str(location_nok),
                                  'ratio': str(failure_rate), })

        # empty scans
        stats_empty: List[
            Tuple[int, Location, str, str, int, int]] = await TrsStatsLocationRawHelper.get_all_empty_scans(
            self._session)
        detection_empty = []
        for count, location, workers_affected, route_type, last_scan, successes in stats_empty:
            detection_empty.append({'lat': str(location.lat),
                                    'lng': str(location.lng),
                                    'worker': str(workers_affected),
                                    'count': str(count),
                                    'type': str(route_type),
                                    'lastscan': str(last_scan),
                                    'countsuccess': str(successes)})

        # Usage
        insta = {}
        usages = []
        idx = 0
        status_name: str = self._get_mad_args().status_name
        stats_usage: List[TrsUsage] = await TrsUsageHelper.get_usages(self._session, last_n_minutes=minutes_usage,
                                                                      instance_name=status_name)
        for usage in stats_usage:
            if 'CPU-' + str(usage.instance) not in insta:
                insta['CPU-' + str(usage.instance)] = {}
                insta['CPU-' + str(usage.instance)]["axis"] = 1
                insta['CPU-' + str(usage.instance)]["data"] = []
            if 'MEM-' + str(usage.instance) not in insta:
                insta['MEM-' + str(usage.instance)] = {}
                insta['MEM-' + str(usage.instance)]['axis'] = 2
                insta['MEM-' + str(usage.instance)]["data"] = []
            if self._get_mad_args().stat_gc:
                if 'CO-' + str(usage.instance) not in insta:
                    insta['CO-' + str(usage.instance)] = {}
                    insta['CO-' + str(usage.instance)]['axis'] = 3
                    insta['CO-' + str(usage.instance)]["data"] = []

            insta['CPU-' + str(usage.instance)]['data'].append([usage.timestamp * 1000, usage.cpu])
            insta['MEM-' + str(usage.instance)]['data'].append([usage.timestamp * 1000, usage.memory])
            if self._get_mad_args().stat_gc:
                insta['CO-' + str(usage.instance)]['data'].append([usage.timestamp * 1000, usage.garbage])

        for label in insta:
            usages.append(
                {'label': label, 'data': insta[label]['data'], 'yaxis': insta[label]['axis'], 'idx': idx})
            idx += 1

        # Gym
        gyms = []
        stats_gyms: Dict[str, int] = await GymHelper.get_gym_count(self._session)
        for team_colour, count in stats_gyms.items():
            if team_colour == TeamColours.BLUE.value:
                color = '#0051CF'
                text = 'Mystic'
            elif team_colour == TeamColours.RED.value:
                color = '#FF260E'
                text = 'Valor'
            elif team_colour == TeamColours.YELLOW.value:
                color = '#FECC23'
                text = 'Instinct'
            else:
                color = '#999999'
                text = 'Uncontested'
            gyms.append({'label': text, 'data': count, 'color': color})

        stats = {'gym': gyms, 'detection_empty': detection_empty, 'usage': usages,
                 'location_info': location_info, 'detection': detection}
        return await self._json_response(stats)
