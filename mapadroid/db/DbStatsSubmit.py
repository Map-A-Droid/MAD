from mapadroid.db.PooledQueryExecutor import PooledQueryExecutor
from mapadroid.utils.logging import logger


class DbStatsSubmit:

    def __init__(self, db_exec: PooledQueryExecutor):
        self._db_exec: PooledQueryExecutor = db_exec

    def submit_stats_complete(self, data):
        query_status = (
            "INSERT INTO trs_stats_detect (worker, timestamp_scan, raid, mon, mon_iv, quest) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
        )
        self._db_exec.executemany(query_status, data, commit=True)
        return True

    def submit_stats_detections_raw(self, data):
        query_status = (
            "INSERT IGNORE INTO trs_stats_detect_raw (worker, type_id, type, count, is_shiny, timestamp_scan) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
        )
        self._db_exec.executemany(query_status, data, commit=True)
        return True

    def submit_stats_locations(self, data):
        query_status = (
            "INSERT IGNORE INTO trs_stats_location (worker, timestamp_scan, location_count, location_ok, location_nok) "
            "VALUES (%s, %s, %s, %s, %s) "
        )
        self._db_exec.executemany(query_status, data, commit=True)
        return True

    def submit_stats_locations_raw(self, data):
        query_status = (
            "INSERT IGNORE INTO trs_stats_location_raw (worker, fix_ts, lat, lng, data_ts, type, walker, "
            "success, period, transporttype) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE count=(count+1)"
        )
        self._db_exec.executemany(query_status, data, commit=True)
        return True

    def cleanup_statistics(self):
        logger.debug("Cleanup statistics tables")
        query = (
            "DELETE FROM trs_stats_detect WHERE timestamp_scan < (UNIX_TIMESTAMP() - 604800)"
        )
        self._db_exec.execute(query, commit=True)

        # stop deleting shiny entries. For science, please (-:
        query = (
            "DELETE FROM trs_stats_detect_raw WHERE timestamp_scan < (UNIX_TIMESTAMP() - 604800) AND is_shiny = 0"
        )
        self._db_exec.execute(query, commit=True)

        query = (
            "DELETE FROM trs_stats_location WHERE timestamp_scan < (UNIX_TIMESTAMP() - 604800)"
        )
        self._db_exec.execute(query, commit=True)

        query = (
            "DELETE FROM trs_stats_location_raw WHERE period < (UNIX_TIMESTAMP() - 604800)"
        )
        self._db_exec.execute(query, commit=True)
