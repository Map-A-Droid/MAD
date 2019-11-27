import sys
from utils.logging import logger
from db.PooledQueryExecutor import PooledQueryExecutor

class DbSanityCheck:
    blacklisted_modes = "NO_ZERO_DATE NO_ZERO_IN_DATE ONLY_FULL_GROUP_BY"

    def __init__(self, db_exec: PooledQueryExecutor):
        self._db_exec: PooledQueryExecutor = db_exec


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
            logger.error("Please drop those settings: {}.", ", ".join(wrong_modes))
            logger.error(
                "More info: https://mad-docs.readthedocs.io/en/latest/common-issues/faq/#sql-mode-error-mysql-strict-mode-mysql-mode")
            sys.exit(1)
