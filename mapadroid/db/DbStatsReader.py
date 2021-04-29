from datetime import datetime, timedelta
from typing import List, Optional

from mapadroid.db.PooledQueryExecutor import PooledQueryExecutor
from mapadroid.utils.logging import LoggerEnums, get_logger, get_origin_logger

logger = get_logger(LoggerEnums.database)


class DbStatsReader:

    def __init__(self, db_exec: PooledQueryExecutor):
        self._db_exec: PooledQueryExecutor = db_exec

    def get_stop_quest(self):
        logger.debug3('Fetching gym count from db')
        query = (
            "SELECT "
            "IF(FROM_UNIXTIME(MIN(trs_quest.quest_timestamp), '%y-%m-%d') IS NULL, 'NO QUEST', "
            "FROM_UNIXTIME(MIN(trs_quest.quest_timestamp), '%y-%m-%d')) AS Quest, "
            "count(pokestop.pokestop_id) AS Count "
            "FROM pokestop LEFT JOIN trs_quest ON pokestop.pokestop_id = trs_quest.GUID "
            "GROUP BY FROM_UNIXTIME(trs_quest.quest_timestamp, '%y-%m-%d')"
        )
        res = self._db_exec.execute(query)
        return res

    def get_quests_count(self, days):
        logger.debug3('Fetching quests count from db')
        query_where = ""
        query_date = "unix_timestamp(DATE_FORMAT(FROM_UNIXTIME(MIN(quest_timestamp)), '%y-%m-%d %k:00:00'))"
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

    def get_all_spawnpoints_count(self):
        logger.debug4("dbWrapper::get_all_spawnpoints_count")
        query = (
            "SELECT count(*) "
            "FROM `trs_spawn`"
        )
        count = self._db_exec.autofetch_value(query)
        return count

    def get_noniv_encounters_count(self, minutes=240):
        logger.info("Fetching get_noniv_encounters_count")
        logger.debug3("Fetching get_noniv_encounters_count from db")
        query_where = 'last_modified > \'%s\' ' % str(datetime.utcnow() - timedelta(minutes=int(minutes)))

        query = (
            "SELECT count(1) as Count, latitude, longitude "
            "FROM pokemon "
            "WHERE cp IS NULL AND %s "
            "GROUP BY latitude, longitude" % (query_where)
        )
        res = self._db_exec.execute(query)
        logger.info("Done fetching get_noniv_encounters_count")
        return res
