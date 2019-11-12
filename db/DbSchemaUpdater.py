import sys
from utils.logging import logger
from db.PooledQueryExecutor import PooledQueryExecutor

class DbSchemaUpdater:

    column_mods = [
        {
            "table": "raid",
            "column": "is_exclusive",
            "ctype": "tinyint(1) NULL"
        },
        {
            "table": "raid",
            "column": "gender",
            "ctype": "tinyint(1) NULL"
        },
        {
            "table": "gym",
            "column": "is_ex_raid_eligible",
            "ctype": "tinyint(1) NOT NULL DEFAULT 0"
        },
        {
            "table": "pokestop",
            "column": "incident_start",
            "ctype": "datetime NULL"
        },
        {
            "table": "pokestop",
            "column": "incident_expiration",
            "ctype": "datetime NULL"
        },
        {
            "table": "pokestop",
            "column": "incident_grunt_type",
            "ctype": "smallint(1) NULL"
        },
        {
            "table": "trs_status",
            "column": "instance",
            "ctype": "VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL FIRST",
            "modify_key": "DROP PRIMARY KEY, ADD PRIMARY KEY (`instance`, `origin`)"
        }
    ]


    def __init__(self, db_exec: PooledQueryExecutor, database: str):
        self._db_exec: PooledQueryExecutor = db_exec
        self._database: str = database


    def ensure_unversioned_columns_exist(self):
        """
        Checks the columns defined in DbSchemaUpdater::column_mods and creates
        them if they don't exist. Exits on error.
        These column_mods are considered "unversioned" because they're not
        covered by util.version.
        :return:
        """
        try:
            for column_mod in self.column_mods:
                self.check_create_column(column_mod)
        except SchemaUpdateError as e:
            column_mod = e.schema_mod
            logger.error("Couldn't create required column {}.{}'", column_mod["table"], column_mod["column"])
            sys.exit(1)


    def check_create_column(self, column_mod: dict):
        if self.check_column_exists(column_mod["table"], column_mod["column"]):
            return
        self.create_column(column_mod)
        if not self.check_column_exists(column_mod["table"], column_mod["column"]):
            raise SchemaUpdateError(column_mod)
        logger.info("Successfully added column '{}.{}'", column_mod["table"], column_mod["column"])


    def create_column(self, column_mod: dict):
        alter_query = (
            "ALTER TABLE {} "
            "ADD COLUMN {} {}"
            .format(column_mod["table"], column_mod["column"], column_mod["ctype"])
        )
        if "modify_key" in column_mod:
            alter_query = alter_query + ", " + column_mod["modify_key"]
        self._db_exec.execute(alter_query, commit=True)


    def check_column_exists(self, table: str, column: str) -> bool:
        query = (
            "SELECT count(*) "
            "FROM information_schema.columns "
            "WHERE table_name = %s "
            "AND column_name = %s "
            "AND table_schema = %s"
        )
        vals = (
            table,
            column,
            self._database,
        )
        return int(self._db_exec.execute(query, vals)[0][0]) == 1


    def check_index_exists(self, table: str, index: str) -> bool:
        query = (
            "SELECT count(*) "
            "FROM information_schema.statistics "
            "WHERE table_name = %s "
            "AND index_name = %s "
            "AND table_schema = %s"
        )
        vals = (
            table,
            index,
            self._database,
        )
        return int(self._db_exec.execute(query, vals)[0][0]) >= 1


class SchemaUpdateError(Exception):

    def __init__(self, schema_mod):
        self.schema_mod = schema_mod
