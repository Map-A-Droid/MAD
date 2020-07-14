import sys
from mapadroid.db.PooledQueryExecutor import PooledQueryExecutor
from . import madmin_conversion
from mapadroid.utils.logging import get_logger, LoggerEnums


logger = get_logger(LoggerEnums.database)


class DbSchemaUpdater:
    """
    Covers methods for database schema updates/additions. It also contains a few
    migrated classes and configurations for schema changes which have been added
    in the past.
    TODO: This needs more refactoring and alingment with `utils/version.py`, and
    it should include a way to create all RocketmapDB tables (basically migrate
    what `scripts/databasesetup.py` does with `scripts/SQL/rocketmap.sql`).
    Also, all SQL configuration should be pulled out.
    """

    table_adds = [
        # Spawn tables
        {
            "table": "trs_spawn",
            "spec": ("`spawnpoint` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL, "
                     "`latitude` double NOT NULL, "
                     "`longitude` double NOT NULL, "
                     "`spawndef` int(11) NOT NULL DEFAULT 240, "
                     "`earliest_unseen` int(6) NOT NULL, "
                     "`last_scanned` datetime DEFAULT NULL, "
                     "`first_detection` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                     "`last_non_scanned` datetime DEFAULT NULL, "
                     "`calc_endminsec` varchar(5) COLLATE utf8mb4_unicode_ci DEFAULT NULL, "
                     "UNIQUE KEY `spawnpoint_2` (`spawnpoint`), "
                     "KEY `spawnpoint` (`spawnpoint`)"
                     )
        },
        {
            "table": "trs_spawnsightings",
            "spec": ("`id` int(11) NOT NULL AUTO_INCREMENT, "
                     "`encounter_id` bigint(20) UNSIGNED NOT NULL, "
                     "`spawnpoint_id` bigint(20) UNSIGNED NOT NULL, "
                     "`scan_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                     "`tth_secs` int(11) DEFAULT NULL, "
                     "PRIMARY KEY (`id`), "
                     "KEY `trs_spawnpointdd_spawnpoint_id` (`spawnpoint_id`)"
                     )
        },
        # Quest table
        {
            "table": "trs_quest",
            "spec": ("`GUID` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL, "
                     "`quest_type` tinyint(3) NOT NULL, "
                     "`quest_timestamp` int(11) NOT NULL, "
                     "`quest_stardust` smallint(4) NOT NULL, "
                     "`quest_pokemon_id` smallint(4) NOT NULL, "
                     "`quest_pokemon_form_id` smallint(6) NOT NULL, "
                     "`quest_pokemon_costume_id` smallint(6) NOT NULL, "
                     "`quest_reward_type` smallint(3) NOT NULL, "
                     "`quest_item_id` smallint(3) NOT NULL, "
                     "`quest_item_amount` tinyint(2) NOT NULL, "
                     "`quest_target` tinyint(3) NOT NULL, "
                     "`quest_condition` varchar(500), "
                     "PRIMARY KEY (`GUID`), "
                     "KEY `quest_type` (`quest_type`)"
                     )
        },
        # Device status table
        {
            "table": "trs_status",
            "spec": ("`origin` VARCHAR(50) NOT NULL , "
                     "`currentPos` VARCHAR(50) NULL DEFAULT NULL, "
                     "`lastPos` VARCHAR(50) NULL DEFAULT NULL, "
                     "`routePos` INT(11) NULL DEFAULT NULL, "
                     "`routeMax` INT(11) NULL DEFAULT NULL, "
                     "`routemanager` VARCHAR(255) NULL DEFAULT NULL, "
                     "`rebootCounter` INT(11) NULL DEFAULT NULL, "
                     "`lastProtoDateTime` VARCHAR(50) NULL DEFAULT NULL, "
                     "`lastPogoRestart` VARCHAR(50) NULL DEFAULT NULL, "
                     "`init` TEXT NOT NULL, "
                     "`rebootingOption` TEXT NOT NULL, "
                     "`restartCounter` TEXT NOT NULL, "
                     "`globalrestartcount` INT(11) NULL DEFAULT 0, "
                     "`lastPogoReboot` VARCHAR(50) NULL DEFAULT NULL , "
                     "`globalrebootcount` INT(11) NULL DEFAULT 0, "
                     "`currentSleepTime` INT(11) NOT NULL DEFAULT 0, "
                     "PRIMARY KEY (`origin`)"
                     )
        },
        # CPU/Memory usage table
        {
            "table": "trs_usage",
            "spec": ("`usage_id` INT(10) AUTO_INCREMENT , "
                     "`instance` varchar(100) NULL DEFAULT NULL, "
                     "`cpu` FLOAT NULL DEFAULT NULL , "
                     "`memory` FLOAT NULL DEFAULT NULL , "
                     "`garbage` INT(5) NULL DEFAULT NULL , "
                     "`timestamp` INT(11) NULL DEFAULT NULL, "
                     "PRIMARY KEY (`usage_id`)"
                     )
        },
        # Statistic tables
        {
            "table": "trs_stats_location_raw",
            "spec": ("`id` int(11) AUTO_INCREMENT, "
                     "`worker` varchar(100) NOT NULL, "
                     "`lat` double NOT NULL, "
                     "`lng` double NOT NULL, "
                     "`fix_ts` int(11) NOT NULL, "
                     "`data_ts` int(11) NOT NULL, "
                     "`type` tinyint(1) NOT NULL, "
                     "`walker` varchar(255) NOT NULL, "
                     "`success` tinyint(1) NOT NULL, "
                     "`period` int(11) NOT NULL, "
                     "`count` int(11) NOT NULL, "
                     "`transporttype` tinyint(1) NOT NULL, "
                     "PRIMARY KEY (`id`),"
                     "KEY `latlng` (`lat`, `lng`),"
                     "UNIQUE `count_same_events` (`worker`, `lat`, `lng`, `type`, `period`)"
                     )
        },
        {
            "table": "trs_stats_location",
            "spec": ("`id` int(11) AUTO_INCREMENT, "
                     "`worker` varchar(100) NOT NULL, "
                     "`timestamp_scan` int(11) NOT NULL, "
                     "`location_count` int(11) NOT NULL, "
                     "`location_ok` int(11) NOT NULL, "
                     "`location_nok` int(11) NOT NULL, "
                     "PRIMARY KEY (`id`), "
                     "KEY worker (`worker`)"
                     )
        },
        {
            "table": "trs_stats_detect_mon_raw",
            "spec": ("`id` int(11) AUTO_INCREMENT, "
                     "`worker` varchar(100) NOT NULL, "
                     "`encounter_id` bigint(20) unsigned NOT NULL, "
                     "`type` varchar(10) NOT NULL, "
                     "`count` int(11) NOT NULL, "
                     "`is_shiny` tinyint(1) NOT NULL DEFAULT 0, "
                     "`timestamp_scan` int(11) NOT NULL, "
                     "PRIMARY KEY (`id`), "
                     "KEY `worker` (`worker`), "
                     "KEY `encounter_id` (`encounter_id`), "
                     "KEY `is_shiny` (`is_shiny`)"
                     )
        },
        {
            "table": "trs_stats_detect_fort_raw",
            "spec": ("`id` int(11) AUTO_INCREMENT, "
                     "`worker` varchar(100) NOT NULL, "
                     "`guid` varchar(50) NOT NULL, "
                     "`type` varchar(10) NOT NULL, "
                     "`count` int(11) NOT NULL, "
                     "`timestamp_scan` int(11) NOT NULL, "
                     "PRIMARY KEY (`id`), "
                     "KEY `worker` (`worker`), "
                     "KEY `guid` (`guid`)"
                     )
        },
        {
            "table": "trs_stats_detect",
            "spec": ("`id` int(100) AUTO_INCREMENT, "
                     "`worker` varchar(100) NOT NULL, "
                     "`timestamp_scan` int(11) NOT NULL, "
                     "`mon` int(255) DEFAULT NULL, "
                     "`raid` int(255) DEFAULT NULL, "
                     "`mon_iv` int(11) DEFAULT NULL, "
                     "`quest` int(100) DEFAULT NULL, "
                     "PRIMARY KEY (`id`), "
                     "KEY worker (`worker`)"
                     )
        }
    ]

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
            "table": "raid",
            "column": "costume",
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
            "table": "trs_quest",
            "column": "quest_pokemon_form_id",
            "ctype": "smallint(6) NOT NULL DEFAULT 0"
        },
        {
            "table": "trs_quest",
            "column": "quest_pokemon_costume_id",
            "ctype": "smallint(6) NOT NULL DEFAULT 0"
        }
    ]

    def __init__(self, db_exec: PooledQueryExecutor, database: str):
        self._db_exec: PooledQueryExecutor = db_exec
        self._database: str = database

    def ensure_unversioned_tables_exist(self):
        """
        Executes the CREATE TABLE IF NOT EXISTS statements defined in
        DbSchemaUpdater::table_adds.
        These modifications are considered "unversioned" because they're not
        covered by util.version.
        :return:
        """
        try:
            for table_add in self.table_adds:
                self.check_create_table(table_add)
        except SchemaUpdateError as e:
            table_add = e.schema_mod
            logger.error("Could't add table {}", table_add["table"])
            sys.exit(1)

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

    def check_create_table(self, table_add: dict):
        sql = ("CREATE TABLE IF NOT EXISTS `{}` "
               "({}) "
               "ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"
               ).format(table_add["table"], table_add["spec"])
        if self._db_exec.execute(sql, commit=True) is None:
            raise SchemaUpdateError(table_add)

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
            "ADD COLUMN {} {}".format(column_mod["table"], column_mod["column"], column_mod["ctype"])
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
        insert_values = (
            table,
            column,
            self._database,
        )
        return int(self._db_exec.execute(query, insert_values)[0][0]) == 1

    def check_index_exists(self, table: str, index: str) -> bool:
        query = (
            "SELECT count(*) "
            "FROM information_schema.statistics "
            "WHERE table_name = %s "
            "AND index_name = %s "
            "AND table_schema = %s"
        )
        insert_values = (
            table,
            index,
            self._database,
        )
        return int(self._db_exec.execute(query, insert_values)[0][0]) >= 1

    def create_madmin_databases_if_not_exists(self):
        for table in madmin_conversion.TABLES:
            self._db_exec.execute(table, commit=True)

    def ensure_unversioned_madmin_columns_exist(self):
        try:
            for column_mod in madmin_conversion.COLUMNS:
                self.check_create_column(column_mod)
        except SchemaUpdateError as e:
            column_mod = e.schema_mod
            logger.error("Couldn't create required column {}.{}'", column_mod["table"], column_mod["column"])
            sys.exit(1)


class SchemaUpdateError(Exception):

    def __init__(self, schema_mod):
        self.schema_mod = schema_mod
