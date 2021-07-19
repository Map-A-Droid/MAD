from datetime import datetime
from typing import List, Optional, Tuple, Dict

from mapadroid.db.helper.TrsStatsDetectHelper import TrsStatsDetectHelper
from mapadroid.db.helper.TrsStatsLocationHelper import TrsStatsLocationHelper
from mapadroid.db.helper.TrsStatsLocationRawHelper import TrsStatsLocationRawHelper
from mapadroid.madmin.endpoints.routes.statistics.AbstractStatistictsRootEndpoint import AbstractStatisticsRootEndpoint
from mapadroid.utils.collections import Location
from mapadroid.utils.geo import get_distance_of_two_points_in_meters


class StatisticsDetectionWorkerDataEndpoint(AbstractStatisticsRootEndpoint):
    """
    "/statistics_detection_worker_data"
    """

    # TODO: Auth
    async def get(self):
        minutes: Optional[int] = self._request.query.get("minutes")
        if minutes:
            minutes = 10
        worker: Optional[str] = self._request.query.get("worker")

        # spawns
        mon = []
        mon_iv = []
        raid = []
        quest = []
        usage = []

        data: Dict[str, Dict[int, Tuple[int, int, int, int]]] = await TrsStatsDetectHelper \
            .get_detection_count_per_worker(self._session,
                                            include_last_n_minutes=minutes,
                                            worker=worker)
        for worker, data_entry in data.items():
            for timestamp, data_of_worker in data_entry.items():
                sum_mons, sum_iv, sum_raids, sum_quests = data_of_worker
                mon.append([timestamp * 1000, sum_mons])
                mon_iv.append([timestamp * 1000, sum_iv])
                raid.append([timestamp * 1000, sum_raids])
                quest.append([timestamp * 1000, sum_quests])
        usage.append({'label': 'Mon', 'data': mon})
        usage.append({'label': 'Mon_IV', 'data': mon_iv})
        usage.append({'label': 'Raid', 'data': raid})
        usage.append({'label': 'Quest', 'data': quest})

        # locations avg
        locations_avg = []

        avg_data_time: Dict[str, Dict[int, List[Tuple[str, int, float, str]]]] = await TrsStatsLocationRawHelper \
            .get_avg_data_time(self._session, include_last_n_minutes=minutes, worker=worker)
        for worker, data_entry in avg_data_time.items():
            for timestamp, worker_location_raw_data in data_entry.items():
                for transport_type_readable, count_of_fix_ts, avg_data_ts, walker in worker_location_raw_data:
                    # dtime is displayed in frontend, not parsing utcfromtimestamp
                    dtime = datetime.fromtimestamp(timestamp).strftime(self._datetimeformat)
                    locations_avg.append(
                        {'dtime': dtime, 'ok_locations': count_of_fix_ts, 'avg_datareceive': avg_data_ts,
                         'transporttype': transport_type_readable, 'type': walker})

        # locations
        ok = []
        nok = []
        sumloc = []
        locations = []
        locations_scanned_by_workers: Dict[str, Dict[int, Tuple[int, int, int]]] = await TrsStatsLocationHelper \
            .get_locations(self._session, include_last_n_minutes=minutes, worker=worker)
        for worker, data_entry in locations_scanned_by_workers.items():
            for timestamp, location_data in data_entry.items():
                location_count, locations_ok, locations_nok = location_data
                ok.append([timestamp * 1000, locations_ok])
                nok.append([timestamp * 1000, locations_nok])
                sumloc.append([timestamp * 1000, location_count])

        locations.append({'label': 'Locations', 'data': sumloc})
        locations.append({'label': 'Locations_ok', 'data': ok})
        locations.append({'label': 'Locations_nok', 'data': nok})

        # dataratio
        loctionratio = []
        location_dataratios: Dict[str, Dict[int, List[Tuple[int, int, int, str]]]] = await TrsStatsLocationRawHelper \
            .get_locations_dataratio(self._session, include_last_n_minutes=minutes, worker=worker)
        if location_dataratios:
            for worker, data_entry in location_dataratios.items():
                for timestamp, data_of_worker in data_entry.items():
                    for count_period, location_type, success, success_locationtype_readable in data_of_worker:
                        loctionratio.append({'label': success_locationtype_readable, 'data': success})
        else:
            loctionratio.append({'label': '', 'data': 0})

        # all spaws
        all_spawns = []
        detection_count_not_grouped: Dict[str, Dict[int, Tuple[int, int, int, int]]] = await TrsStatsDetectHelper \
            .get_detection_count_per_worker(self._session, hourly=False, worker=worker)
        mon_spawn_count: int = 0
        mon_iv_count: int = 0
        raid_count: int = 0
        quest_count: int = 0
        for worker, data_entry in detection_count_not_grouped.items():
            for timestamp, data_of_worker in data_entry.items():
                sum_mons, sum_iv, sum_raids, sum_quests = data_of_worker
                mon_spawn_count += sum_mons
                mon_iv_count += sum_iv
                raid_count += sum_raids
                quest_count += sum_quests
        all_spawns.append({'type': 'Mon', 'amount': mon_spawn_count})
        all_spawns.append({'type': 'Mon_IV', 'amount': mon_iv_count})
        all_spawns.append({'type': 'Raid', 'amount': raid_count})
        all_spawns.append({'type': 'Quest', 'amount': quest_count})

        # location raw
        location_raw = []
        last_lat = 0
        last_lng = 0
        distance: float = -1.0
        raw_location_details: List[Tuple[Location, str, str, int, int, str]] = await TrsStatsLocationRawHelper \
            .get_location_raw(self._session, include_last_n_minutes=minutes, worker=worker)
        for (location, location_type_str, success_str, timestamp_fix, timestamp_data_or_fix,
             transport_type_readable) in raw_location_details:
            if last_lat != 0 and last_lng != 0:
                distance = round(get_distance_of_two_points_in_meters(last_lat, last_lng,
                                                                      location.lat, location.lng),
                                 2)
                last_lat = location.lat
                last_lng = location.lng
            if last_lat == 0 and last_lng == 0:
                last_lat = location.lat
                last_lng = location.lng
            if location.lat == 0 and location.lng == 0:
                distance = -1.0

            location_raw.append(
                {'lat': location.lat, 'lng': location.lng, 'distance': distance, 'type': location_type_str,
                 'data': success_str,
                 # fix_ts and data_ts is displayed in frontend, not parsing utcfromtimestamp
                 'fix_ts': datetime.fromtimestamp(timestamp_fix).strftime(self._datetimeformat),
                 'data_ts': datetime.fromtimestamp(timestamp_data_or_fix).strftime(self._datetimeformat),
                 'transporttype': transport_type_readable})

        workerstats = {'avg': locations_avg, 'receiving': usage, 'locations': locations,
                       'ratio': loctionratio, 'allspawns': all_spawns,
                       'location_raw': location_raw}
        return await self._json_response(workerstats)
