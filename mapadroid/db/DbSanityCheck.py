import sys
from mapadroid.db.PooledQueryExecutor import PooledQueryExecutor
from mapadroid.utils import global_variables
from mapadroid.utils.logging import get_logger, LoggerEnums


logger = get_logger(LoggerEnums.database)


class DbSanityCheck:
    blacklisted_modes = "NO_ZERO_DATE NO_ZERO_IN_DATE"

    def __init__(self, db_exec: PooledQueryExecutor):
        self._db_exec: PooledQueryExecutor = db_exec
        self.failing_issues = False
        self.supports_apks = False

    def check_all(self):
        self.ensure_correct_sql_mode()
        self.validate_max_allowed_packet()
        if self.failing_issues:
            sys.exit(1)

    def ensure_correct_sql_mode(self):
        """
        Checks whether Mysql's SQL_MODE is valid. Exits on error.
        :return:
        """
        query = "SELECT @@GLOBAL.sql_mode"
        res = self._db_exec.execute(query)[0][0]
        detected_wrong_modes = []
        for mode in self.blacklisted_modes.split():
            if mode in res:
                detected_wrong_modes.append(mode)
        if len(detected_wrong_modes) > 0:
            logger.error("Your MySQL/MariaDB sql_mode settings needs an adjustment.")
            logger.error("Please drop those settings: {}.", ", ".join(detected_wrong_modes))
            logger.error(
                "More info: https://mad-docs.readthedocs.io/en/latest/faq/#sql-mode-error-mysql-strict-mode-mysql-mode")
            self.failing_issues = True

    def validate_max_allowed_packet(self):
        query = "SELECT @@global.max_allowed_packet"
        res = self._db_exec.autofetch_value(query)
        if res < global_variables.CHUNK_MAX_SIZE:
            logger.error("max_allowed_packet may need to be adjusted to use the MAD APK feature")
            logger.error(
                "MAD will function without this being set but you will be unable to upload and serve MAD APK files")
            logger.error(
                "More info can be found @ https://dev.mysql.com/doc/refman/8.0/en/program-variables.html")
        else:
            self.supports_apks = True
