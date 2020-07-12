from typing import Optional, List

from datetime import datetime, timedelta
from mapadroid.db.PooledQueryExecutor import PooledQueryExecutor
from mapadroid.utils.logging import get_logger, LoggerEnums, get_origin_logger


logger = get_logger(LoggerEnums.database)


class DbStatsReader:

    def __init__(self, db_exec: PooledQueryExecutor):
        self._db_exec: PooledQueryExecutor = db_exec

    def get_shiny_stats(self):
        logger.debug3('Fetching shiny pokemon stats from db')
        query = (
            "SELECT (select count(DISTINCT pokemon.encounter_id) from pokemon inner join trs_stats_detect_mon_raw on "
            "trs_stats_detect_mon_raw.encounter_id=pokemon.encounter_id where pokemon.pokemon_id=a.pokemon_id and "
            "trs_stats_detect_mon_raw.worker=b.worker and pokemon.form=a.form), count(DISTINCT a.encounter_id), "
            "a.pokemon_id, b.worker, GROUP_CONCAT(DISTINCT a.encounter_id "
            "ORDER BY a.encounter_id DESC SEPARATOR '<br>'), a.form, b.timestamp_scan "
            "FROM pokemon a left join trs_stats_detect_mon_raw b on a.encounter_id=b.encounter_id "
            "WHERE b.is_shiny=1 group by "
            "b.is_shiny, a.pokemon_id, a.form, b.worker order by b.timestamp_scan DESC "
        )
        res = self._db_exec.execute(query)
        return res

    def get_shiny_stats_v2(self, timestamp_from: int, timestamp_to: int):
        logger.debug3('Fetching shiny_stats_v2 pokemon stats from db from {} to {}', timestamp_from, timestamp_to)
        data = ()

        query = (
            "SELECT pokemon.pokemon_id, pokemon.form, pokemon.latitude, pokemon.longitude, pokemon.gender, "
            "pokemon.costume, tr.count, tr.timestamp_scan, tr.worker, pokemon.encounter_id "
            "FROM pokemon "
            "JOIN trs_stats_detect_mon_raw tr on tr.encounter_id=pokemon.encounter_id "
            "WHERE tr.is_shiny=1 "
        )

        if timestamp_from:
            query = query + "AND UNIX_TIMESTAMP(last_modified) > %s "
            data = data + (timestamp_from,)
        if timestamp_to:
            query = query + "AND UNIX_TIMESTAMP(last_modified) < %s "
            data = data + (timestamp_to,)
        query = query + " GROUP BY pokemon.encounter_id ORDER BY tr.timestamp_scan DESC"
        logger.debug4('data: {}', data)
        res = self._db_exec.execute(query, data)
        return res

    def get_shiny_stats_global_v2(self, mon_id_list: set, timestamp_from: int, timestamp_to: int):
        logger.debug3('Fetching shiny_stats_global_v2')
        data = ()

        query = (
            "SELECT count(*), pokemon_id, form, gender, costume FROM pokemon WHERE individual_attack IS NOT NULL "
        )
        query = query + "AND pokemon_id IN(" + ",".join(map(str, mon_id_list)) + ") "
        if timestamp_from:
            query = query + " AND UNIX_TIMESTAMP(last_modified) > %s "
            data = data + (timestamp_from,)
        if timestamp_to:
            query = query + " AND UNIX_TIMESTAMP(last_modified) < %s "
            data = data + (timestamp_to,)
        query = query + "GROUP BY pokemon_id, form"
        res = self._db_exec.execute(query, data)
        return res

    def get_detection_count(self, minutes=False, grouped=True, worker=False):
        tmp_logger = get_origin_logger(logger, origin=worker)
        tmp_logger.debug3('Fetching group detection count from db')
        grouped_query = ""
        worker_where = ""
        if worker and minutes:
            worker_where = ' and worker = \'%s\' ' % str(worker)
        if worker and not minutes:
            worker_where = ' where worker = \'%s\' ' % str(worker)
        if grouped:
            grouped_query = ", day(FROM_UNIXTIME(timestamp_scan)), hour(FROM_UNIXTIME(timestamp_scan))"
        query_where = ''
        query_date = "unix_timestamp(DATE_FORMAT(from_unixtime(timestamp_scan), '%y-%m-%d %k:00:00'))"
        if minutes:
            minutes = datetime.now().replace(
                minute=0, second=0, microsecond=0) - timedelta(minutes=int(minutes))
            query_where = ' where (timestamp_scan) >= unix_timestamp(\'%s\') ' % str(minutes)

        query = (
            "SELECT  %s, worker, sum(mon) as Mon, sum(mon_iv) as MonIV, sum(raid) as Raids, sum(quest) as Quests "
            "FROM trs_stats_detect %s %s "
            "GROUP BY worker %s "
            "ORDER BY timestamp_scan" %
            (str(query_date), str(query_where), str(worker_where), str(grouped_query))
        )
        res = self._db_exec.execute(query)

        return res

    def get_shiny_stats_hour(self):
        logger.debug3('Fetching shiny pokemon stats from db')
        query = (
            "SELECT hour(FROM_UNIXTIME(timestamp_scan)) AS hour, encounter_id as type_id "
            "FROM trs_stats_detect_mon_raw "
            "WHERE is_shiny = 1 "
            "GROUP BY encounter_id, hour ORDER BY hour ASC"
        )
        res = self._db_exec.execute(query)
        return res

    def get_avg_data_time(self, minutes=False, grouped=True, worker=False):
        tmp_logger = get_origin_logger(logger, origin=worker)
        tmp_logger.debug3('Fetching group detection count from db')
        grouped_query = ""
        query_where = ""
        worker_where = ""
        if worker:
            worker_where = ' and worker = \'%s\' ' % str(worker)
        if grouped:
            grouped_query = ", day(FROM_UNIXTIME(period)), hour(FROM_UNIXTIME(period)), transporttype"
        if minutes:
            minutes = datetime.now().replace(
                minute=0, second=0, microsecond=0) - timedelta(minutes=int(minutes))
            query_where = ' and (period) >= unix_timestamp(\'%s\') ' % str(minutes)

        query_date = "unix_timestamp(DATE_FORMAT(FROM_UNIXTIME(period), '%y-%m-%d %k:00:00'))"

        query = (
            "SELECT %s, if(transporttype=0,'Teleport',if(transporttype=1,'Walk', "
            "'other')), worker, count(fix_ts), avg(data_ts-fix_ts) as data_time, walker from trs_stats_location_raw "
            "where success=1 and type in (0,1) and (walker='mon_mitm' or walker='iv_mitm' or walker='pokestops') "
            "%s %s group by worker %s" %
            (str(query_date), (query_where), str(worker_where), str(grouped_query))
        )

        res = self._db_exec.execute(query)

        return res

    def get_locations(self, minutes=False, grouped=True, worker=False):
        tmp_logger = get_origin_logger(logger, origin=worker)
        tmp_logger.debug3('Fetching group locations count from db')
        grouped_query = ""
        query_where = ""
        worker_where = ""
        if worker and minutes:
            worker_where = ' and worker = \'%s\' ' % str(worker)
        if worker and not minutes:
            worker_where = ' where worker = \'%s\' ' % str(worker)
        if grouped:
            grouped_query = ", day(FROM_UNIXTIME(timestamp_scan)), hour(FROM_UNIXTIME(timestamp_scan))"
        if minutes:
            minutes = datetime.now().replace(
                minute=0, second=0, microsecond=0) - timedelta(minutes=int(minutes))
            query_where = ' where (timestamp_scan) >= unix_timestamp(\'%s\') ' % str(minutes)

        query_date = "unix_timestamp(DATE_FORMAT(FROM_UNIXTIME(timestamp_scan), '%y-%m-%d %k:00:00'))"

        query = (
            "SELECT %s, worker, sum(location_count), sum(location_ok), sum(location_nok) from trs_stats_location "
            " %s %s group by worker %s" %
            (str(query_date), (query_where), str(worker_where), str(grouped_query))
        )
        res = self._db_exec.execute(query)

        return res

    def get_locations_dataratio(self, minutes=False, grouped=True, worker=False):
        tmp_logger = get_origin_logger(logger, origin=worker)
        tmp_logger.debug3('Fetching group locations dataratio from db')
        grouped_query = ""
        query_where = ""
        worker_where = ""
        if worker and minutes:
            worker_where = ' and worker = \'%s\' ' % str(worker)
        if worker and not minutes:
            worker_where = ' where worker = \'%s\' ' % str(worker)
        if grouped:
            grouped_query = ", success, type"
        if minutes:
            minutes = datetime.now().replace(
                minute=0, second=0, microsecond=0) - timedelta(minutes=int(minutes))
            query_where = ' where (period) >= unix_timestamp(\'%s\') ' % str(minutes)

        query_date = "unix_timestamp(DATE_FORMAT(FROM_UNIXTIME(period), '%y-%m-%d %k:00:00'))"

        query = (
            "SELECT %s, worker, count(period), if(type=0,if(success=1,'OK-Normal','NOK-Normal'),"
            "if(success=1,'OK-PrioQ','NOK-PrioQ')) from trs_stats_location_raw "
            " %s %s and type in(0,1) group by worker %s" %
            (str(query_date), (query_where), str(worker_where), str(grouped_query))
        )

        res = self._db_exec.execute(query)

        return res

    def get_all_empty_scans(self):
        logger.debug3('Fetching all empty locations from db')
        query = (
            "SELECT count(b.id) as Count, b.lat, b.lng, GROUP_CONCAT(DISTINCT b.worker order by worker asc "
            "SEPARATOR ', '), if(b.type=0,'Normal','PrioQ'), max(b.period), (select count(c.id) "
            "from trs_stats_location_raw c where c.lat=b.lat and c.lng=b.lng and c.success=1) as successcount from "
            "trs_stats_location_raw b where success=0 group by lat, lng HAVING Count > 5 and successcount=0 "
            "ORDER BY count(id) DESC"
        )
        res = self._db_exec.execute(query)
        return res

    def get_detection_raw(self, minutes=False, worker=False) -> (Optional[List[dict]], Optional[List[dict]]):
        tmp_logger = get_origin_logger(logger, origin=worker)
        tmp_logger.debug3('Fetching detetion raw data from db')
        query_where = ""
        worker_where = ""
        if worker and minutes:
            worker_where = ' and worker = \'%s\' ' % str(worker)
        if worker and not minutes:
            worker_where = ' where worker = \'%s\' ' % str(worker)
        if minutes:
            minutes = datetime.now().replace(
                minute=0, second=0, microsecond=0) - timedelta(minutes=int(minutes))
            query_where = ' where (timestamp_scan) >= unix_timestamp(\'%s\') ' % str(minutes)

        query_date = "unix_timestamp(DATE_FORMAT(FROM_UNIXTIME(timestamp_scan), '%y-%m-%d %k:00:00'))"

        query = (
            "SELECT %s, type, encounter_id as type_id, count FROM trs_stats_detect_mon_raw %s %s order by id asc" %
            (str(query_date), (query_where), str(worker_where))
        )
        query2 = (
            "SELECT %s, type, guid as type_id, count FROM trs_stats_detect_fort_raw %s %s order by id asc" %
            (str(query_date), (query_where), str(worker_where))
        )

        res = self._db_exec.execute(query)
        res2 = self._db_exec.execute(query2)
        return res, res2

    def get_location_raw(self, minutes=False, worker=False):
        tmp_logger = get_origin_logger(logger, origin=worker)
        tmp_logger.debug3('Fetching locations raw data from db')
        query_where = ""
        worker_where = ""
        if worker and minutes:
            worker_where = ' and worker = \'%s\' ' % str(worker)
        if worker and not minutes:
            worker_where = ' where worker = \'%s\' ' % str(worker)
        if minutes:
            minutes = datetime.now().replace(
                minute=0, second=0, microsecond=0) - timedelta(minutes=int(minutes))
            query_where = ' where (period) >= unix_timestamp(\'%s\') ' % str(minutes)

        query_date = "unix_timestamp(DATE_FORMAT(FROM_UNIXTIME(period), '%y-%m-%d %k:00:00'))"

        query = (
            "SELECT %s, lat, lng, if(type=0,'Normal',if(type=1,'PrioQ', if(type=2,'Startup',"
            "if(type=3,'Reboot','Restart')))), if(success=1,'OK','NOK'), fix_ts, "
            "if(data_ts=0,fix_ts,data_ts), count, if(transporttype=0,'Teleport',if(transporttype=1,'Walk', "
            "'other')) from trs_stats_location_raw %s %s order by id asc" %
            (str(query_date), (query_where), str(worker_where))
        )

        res = self._db_exec.execute(query)
        return res

    def get_location_info(self):
        logger.debug3('Fetching all empty locations from db')
        query = (
            "SELECT worker, sum(location_count), sum(location_ok), sum(location_nok), "
            "sum(location_nok) / sum(location_count) * 100 as Loc_fail_rate "
            "FROM trs_stats_location "
            "GROUP BY worker"
        )
        res = self._db_exec.execute(query)
        return res

    def get_pokemon_count(self, minutes):
        logger.debug3('Fetching pokemon spawns count from db')
        query_where = ''
        query_date = "UNIX_TIMESTAMP(DATE_FORMAT(last_modified, '%y-%m-%d %k:00:00')) as timestamp"
        if minutes:
            minutes = datetime.utcnow().replace(
                minute=0, second=0, microsecond=0) - timedelta(minutes=int(minutes))
            query_where = ' where last_modified > \'%s\' ' % str(minutes)

        query = (
            "SELECT %s, count(DISTINCT encounter_id) as Count, if(CP is NULL, 0, 1) as IV "
            "FROM pokemon "
            " %s "
            "GROUP BY IV, day(TIMESTAMP(last_modified)), hour(TIMESTAMP(last_modified)) "
            "ORDER BY timestamp" % (str(query_date), str(query_where))
        )
        res = self._db_exec.execute(query)
        return res

    def get_best_pokemon_spawns(self):
        logger.debug3('Fetching best pokemon spawns from db')
        query = (
            "SELECT encounter_id, pokemon_id, unix_timestamp(last_modified), "
            "individual_attack, individual_defense, individual_stamina, cp_multiplier, "
            "cp, form, costume "
            "FROM pokemon "
            "WHERE individual_attack = 15 and individual_defense = 15 and individual_stamina = 15 "
            "ORDER BY last_modified DESC LIMIT 300"
        )
        res = self._db_exec.execute(query)
        return res

    def get_gym_count(self):
        logger.debug3('Fetching gym count from db')
        query = (
            "SELECT If(team_id=0, 'WHITE', if(team_id=1, 'BLUE', if (team_id=2, 'RED', 'YELLOW'))) "
            "AS Color, count(team_id) AS Count "
            "FROM `gym` "
            "GROUP BY team_id"
        )
        res = self._db_exec.execute(query)
        return res

    def get_stop_quest(self):
        logger.debug3('Fetching gym count from db')
        query = (
            "SELECT "
            "If(FROM_UNIXTIME(trs_quest.quest_timestamp, '%y-%m-%d') IS NULL, 'NO QUEST', "
            "FROM_UNIXTIME(trs_quest.quest_timestamp, '%y-%m-%d')) AS Quest, "
            "count(pokestop.pokestop_id) AS Count "
            "FROM pokestop LEFT JOIN trs_quest ON pokestop.pokestop_id = trs_quest.GUID "
            "GROUP BY FROM_UNIXTIME(trs_quest.quest_timestamp, '%y-%m-%d')"
        )
        res = self._db_exec.execute(query)
        return res

    def get_quests_count(self, days):
        logger.debug3('Fetching quests count from db')
        query_where = ""
        query_date = "unix_timestamp(DATE_FORMAT(FROM_UNIXTIME(quest_timestamp), '%y-%m-%d %k:00:00'))"
        if days:
            days = datetime.utcnow() - timedelta(days=days)
            query_where = "WHERE FROM_UNIXTIME(quest_timestamp) > '%s' " % str(days)
        query = (
            "SELECT %s, count(GUID) as Count FROM trs_quest %s "
            "GROUP BY day(FROM_UNIXTIME(quest_timestamp)), hour(FROM_UNIXTIME(quest_timestamp)) "
            "ORDER BY quest_timestamp" % (str(query_date), str(query_where))
        )
        res = self._db_exec.execute(query)
        return res

    def get_usage_count(self, minutes=120, instance=None):
        logger.debug3('Fetching usage from db')
        query_where = ''
        if minutes:
            days = datetime.now() - timedelta(minutes=int(minutes))
            query_where = "WHERE FROM_UNIXTIME(timestamp) > '%s' " % str(days)
        if instance is not None:
            query_where = query_where + " AND instance = '%s' " % str(instance)
        query = (
            "SELECT cpu, memory, garbage, timestamp, instance "
            "FROM trs_usage %s "
            "ORDER BY timestamp" % (str(query_where))
        )
        res = self._db_exec.execute(query)
        return res

    def check_stop_quest_level(self, worker, latitude, longitude):
        tmp_logger = get_origin_logger(logger, origin=worker)
        tmp_logger.debug3("DbWrapper::check_stop_quest_level called")
        query = (
            "SELECT trs_stats_detect_fort_raw.guid "
            "FROM trs_stats_detect_fort_raw "
            "INNER JOIN pokestop ON pokestop.pokestop_id = trs_stats_detect_fort_raw.guid "
            "WHERE pokestop.latitude=%s AND pokestop.longitude=%s AND trs_stats_detect_fort_raw.worker=%s LIMIT 1"
        )
        data = (latitude, longitude, worker)

        res = self._db_exec.execute(query, data)
        number_of_rows = len(res)
        if number_of_rows > 0:
            logger.debug('Pokestop already visited')
            return True
        else:
            logger.debug('Pokestop not visited till now')
            return False

    def get_all_spawnpoints_count(self):
        logger.debug4("dbWrapper::get_all_spawnpoints_count")
        query = (
            "SELECT count(*) "
            "FROM `trs_spawn`"
        )
        count = self._db_exec.autofetch_value(query)
        return count
