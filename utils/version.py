import json
import sys

from utils.logging import logger

from .convert_mapping import convert_mappings

current_version = 13


class MADVersion(object):
    def __init__(self, args, dbwrapper):
        self._application_args = args
        self.dbwrapper = dbwrapper
        self._version = 0

    def get_version(self):
        try:
            # checking mappings.json
            convert_mappings()
            with open('version.json') as f:
                versio = json.load(f)
            self._version = int(versio['version'])
            if int(self._version) < int(current_version):
                logger.error('New Update found')
                self.start_update()
        except FileNotFoundError:
            self.set_version(0)
            self.start_update()

    def start_update(self):

        if self._version < 1:
            logger.info('Execute Update for Version 1')
            # Adding quest_reward for PMSF ALT
            if self.dbwrapper.check_column_exists('trs_quest', 'quest_reward') == 0:
                alter_query = (
                    "ALTER TABLE trs_quest "
                    "ADD quest_reward VARCHAR(500) NULL AFTER quest_condition"
                )
                try:
                    self.dbwrapper.execute(alter_query, commit=True)
                except Exception as e:
                    logger.info("Unexpected error: {}", e)

            # Adding quest_task = ingame quest conditions
            if self.dbwrapper.check_column_exists('trs_quest', 'quest_task') == 0:
                alter_query = (
                    "ALTER TABLE trs_quest "
                    "ADD quest_task VARCHAR(150) NULL AFTER quest_reward"
                )
                try:
                    self.dbwrapper.execute(alter_query, commit=True)
                except Exception as e:
                    logger.info("Unexpected error: {}", e)

            # Adding form column if it doesnt exist
            if self._application_args.db_method == "rm":
                alter_query = (
                    "ALTER TABLE raid "
                    "ADD form smallint(6) DEFAULT NULL"
                )
                column_exist = self.dbwrapper.check_column_exists(
                    'raid', 'form')
            else:
                logger.error("Invalid db_method in config. Exiting")
                sys.exit(1)

            if column_exist == 0:
                try:
                    self.dbwrapper.execute(alter_query, commit=True)
                except Exception as e:
                    logger.info("Unexpected error: {}", e)

        if self._version < 2:
            alter_query = (
                "ALTER TABLE trs_quest "
                "CHANGE quest_reward "
                "quest_reward VARCHAR(1000) NULL DEFAULT NULL"
            )
            try:
                self.dbwrapper.execute(alter_query, commit=True)
            except Exception as e:
                logger.info("Unexpected error: {}", e)
        if self._version < 7:
            alter_query = (
                "ALTER TABLE trs_status "
                "ADD lastPogoReboot varchar(50) NULL DEFAULT NULL"
            )
            column_exist = self.dbwrapper.check_column_exists(
                'trs_status', 'lastPogoReboot')
            if column_exist == 0:
                try:
                    self.dbwrapper.execute(alter_query, commit=True)
                except Exception as e:
                    logger.info("Unexpected error: {}", e)

            alter_query = (
                "ALTER TABLE trs_status "
                "ADD globalrebootcount int(11) NULL DEFAULT '0'"
            )
            column_exist = self.dbwrapper.check_column_exists(
                'trs_status', 'globalrebootcount')
            if column_exist == 0:
                try:
                    self.dbwrapper.execute(alter_query, commit=True)
                except Exception as e:
                    logger.info("Unexpected error: {}", e)

            alter_query = (
                "ALTER TABLE trs_status "
                "ADD globalrestartcount int(11) NULL DEFAULT '0'"
            )
            column_exist = self.dbwrapper.check_column_exists(
                'trs_status', 'globalrestartcount')
            if column_exist == 0:
                try:
                    self.dbwrapper.execute(alter_query, commit=True)
                except Exception as e:
                    logger.info("Unexpected error: {}", e)

            alter_query = (
                "ALTER TABLE trs_status CHANGE lastPogoRestart "
                "lastPogoRestart VARCHAR(50) NULL DEFAULT NULL"
            )
            try:
                self.dbwrapper.execute(alter_query, commit=True)
            except Exception as e:
                logger.info("Unexpected error: {}", e)

            alter_query = (
                "ALTER TABLE trs_status "
                "CHANGE currentPos currentPos VARCHAR(50) NULL DEFAULT NULL, "
                "CHANGE lastPos lastPos VARCHAR(50) NULL DEFAULT NULL, "
                "CHANGE routePos routePos INT(11) NULL DEFAULT NULL, "
                "CHANGE routeMax routeMax INT(11) NULL DEFAULT NULL, "
                "CHANGE rebootingOption rebootingOption TEXT NULL, "
                "CHANGE rebootCounter rebootCounter INT(11) NULL DEFAULT NULL, "
                "CHANGE routemanager routemanager VARCHAR(255) NULL DEFAULT NULL, "
                "CHANGE lastProtoDateTime lastProtoDateTime VARCHAR(50), "
                "CHANGE lastPogoRestart lastPogoRestart VARCHAR(50), "
                "CHANGE init init TEXT NULL, "
                "CHANGE restartCounter restartCounter TEXT NULL"
            )
            try:
                self.dbwrapper.execute(alter_query, commit=True)
            except Exception as e:
                logger.info("Unexpected error: {}", e)

        if self._version < 8:
            alter_query = (
                "ALTER TABLE trs_quest "
                "ADD quest_template VARCHAR(100) NULL DEFAULT NULL "
                "AFTER quest_reward"
            )
            column_exist = self.dbwrapper.check_column_exists(
                'trs_quest', 'quest_template')
            if column_exist == 0:
                try:
                    self.dbwrapper.execute(alter_query, commit=True)
                except Exception as e:
                    logger.exception("Unexpected error: {}", e)

        if self._version < 9:
            alter_query = (
                "UPDATE trs_quest "
                "SET quest_condition=REPLACE(quest_condition,'\\\"','\"'),"
                " quest_reward=REPLACE(quest_reward,'\\\"','\"')"
            )
            try:
                self.dbwrapper.execute(alter_query, commit=True)
            except Exception as e:
                logger.exception("Unexpected error: {}", e)

        if self._version < 10:
            query = (
                "CREATE TABLE IF NOT EXISTS trs_s2cells ( "
                "id bigint(20) unsigned NOT NULL, "
                "level int(11) NOT NULL, "
                "center_latitude double NOT NULL, "
                "center_longitude double NOT NULL, "
                "updated int(11) NOT NULL, "
                "PRIMARY KEY (id)) "
            )
            try:
                self.dbwrapper.execute(query, commit=True)
            except Exception as e:
                logger.exception("Unexpected error: {}", e)

        if self._version < 11:
            query = (
                "ALTER TABLE trs_stats_detect_raw "
                "ADD is_shiny TINYINT(1) NOT NULL DEFAULT '0' "
                "AFTER count"
            )
            column_exist = self.dbwrapper.check_column_exists(
                'trs_stats_detect_raw', 'is_shiny')
            if column_exist == 0:
                try:
                    self.dbwrapper.execute(query, commit=True)
                except Exception as e:
                    logger.exception("Unexpected error: {}", e)

        if self._version < 12:
            query = (
                "ALTER TABLE trs_stats_detect_raw "
                "ADD INDEX typeworker (worker, type_id)"
            )
            index_exist = self.dbwrapper.check_index_exists(
                'trs_stats_detect_raw', 'typeworker')

            if index_exist >= 1:
                query = (
                    "ALTER TABLE trs_stats_detect_raw DROP INDEX typeworker, ADD INDEX typeworker (worker, type_id)"
                )
            try:
                self.dbwrapper.execute(query, commit=True)
            except Exception as e:
                logger.exception("Unexpected error: {}", e)

            query = (
                "ALTER TABLE trs_stats_detect_raw "
                "ADD INDEX shiny (is_shiny)"
            )
            index_exist = self.dbwrapper.check_index_exists(
                'trs_stats_detect_raw', 'shiny')

            if index_exist >= 1:
                query = (
                    "ALTER TABLE trs_stats_detect_raw DROP INDEX shiny, ADD INDEX shiny (is_shiny)"
                )
            try:
                self.dbwrapper.execute(query, commit=True)
            except Exception as e:
                logger.exception("Unexpected error: {}", e)

        if self._version < 13:
            # Adding current_sleep for worker status
            if self.dbwrapper.check_column_exists('trs_status', 'currentSleepTime') == 0:
                query = (
                    "ALTER TABLE trs_status "
                    "ADD currentSleepTime INT(11) NOT NULL DEFAULT 0"
                )
                try:
                    self.dbwrapper.execute(query, commit=True)
                except Exception as e:
                    logger.exception("Unexpected error: {}", e)

        self.set_version(current_version)

    def set_version(self, version):
        output = {'version': version}
        with open('version.json', 'w') as outfile:
            json.dump(output, outfile)
