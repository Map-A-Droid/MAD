import json
import logging
import requests
import sys

log = logging.getLogger(__name__)

current_version = 7


class MADVersion(object):
    def __init__(self, args, dbwrapper):
        self._application_args = args
        self._dbwrapper = dbwrapper
        self._version = 0

    def get_version(self):
        try:
            with open('version.json') as f:
                versio = json.load(f)
            self._version = versio['version']
            if self._version< current_version:
                log.error('New Update found')
                self.start_update()
        except FileNotFoundError as e:
            self.set_version(0)
            self.start_update()
            
    def start_update(self):
        if self._version < 1:
            log.info('Execute Update for Version 1')
            # Adding quest_reward for PMSF ALT
            if self._dbwrapper.check_column_exists('trs_quest', 'quest_reward') == 0:
                alter_query = (
                    "ALTER TABLE trs_quest "
                    "ADD quest_reward VARCHAR(500) NULL AFTER quest_condition"
                )
                try:
                    self._dbwrapper.execute(alter_query, commit=True)
                except Exception as e:
                    log.info("Unexpected error: %s" % e)

            # Adding quest_task = ingame quest conditions
            if self._dbwrapper.check_column_exists('trs_quest', 'quest_task') == 0:
                alter_query = (
                    "ALTER TABLE trs_quest "
                    "ADD quest_task VARCHAR(150) NULL AFTER quest_reward"
                )
                try:
                    self._dbwrapper.execute(alter_query, commit=True)
                except Exception as e:
                    log.info("Unexpected error: %s" % e)
            
            # Adding form column for rm / monocle if not exists
            if self._application_args.db_method == "rm":
                alter_query = (
                    "ALTER TABLE raid "
                    "ADD form smallint(6) DEFAULT NULL"
                )
                column_exist = self._dbwrapper.check_column_exists('raid', 'form')
            elif self._application_args.db_method == "monocle":
                alter_query = (
                    "ALTER TABLE raids "
                    "ADD form smallint(6) DEFAULT NULL"
                )
                column_exist = self._dbwrapper.check_column_exists('raids', 'form')
            else:
                log.error("Invalid db_method in config. Exiting")
                sys.exit(1)   
            
            if column_exist == 0:
                try:
                    self._dbwrapper.execute(alter_query, commit=True)
                except Exception as e:
                    log.info("Unexpected error: %s" % e)
                    
        if self._version < 2:
            alter_query = (
                "ALTER TABLE trs_quest "
                "CHANGE quest_reward "
                "quest_reward VARCHAR(1000) NULL DEFAULT NULL"
            )
            try:
                self._dbwrapper.execute(alter_query, commit=True)
            except Exception as e:
                log.info("Unexpected error: %s" % e)
        if self._version < 3:
            if self._application_args.db_method == "monocle":
                # Add Weather Index
                alter_query = (
                    "ALTER TABLE weather ADD UNIQUE s2_cell_id (s2_cell_id) USING BTREE"
                )
                try:
                    self._dbwrapper.execute(alter_query, commit=True)
                except Exception as e:
                    log.info("Unexpected error: %s" % e)

                # Change Mon Unique Index
                alter_query = (
                    "ALTER TABLE sightings DROP INDEX timestamp_encounter_id_unique"
                )
                try:
                    self._dbwrapper.execute(alter_query, commit=True)
                except Exception as e:
                    log.info("Unexpected error: %s" % e)

                alter_query = (
                    "ALTER TABLE sightings DROP INDEX encounter_id;"
                )
                try:
                    self._dbwrapper.execute(alter_query, commit=True)
                except Exception as e:
                    log.info("Unexpected error: %s" % e)

                alter_query = (
                    "CREATE TABLE sightings_temp LIKE sightings;"
                )
                try:
                    self._dbwrapper.execute(alter_query, commit=True)
                except Exception as e:
                    log.info("Unexpected error: %s" % e)

                alter_query = (
                    "ALTER TABLE sightings_temp ADD UNIQUE(encounter_id);"
                )
                try:
                    self._dbwrapper.execute(alter_query, commit=True)
                except Exception as e:
                    log.info("Unexpected error: %s" % e)

                alter_query = (
                    "INSERT IGNORE INTO sightings_temp SELECT * FROM sightings ORDER BY id;"
                )
                try:
                    self._dbwrapper.execute(alter_query, commit=True)
                except Exception as e:
                    log.info("Unexpected error: %s" % e)

                alter_query = (
                    "RENAME TABLE sightings TO backup_sightings, sightings_temp TO sightings;"
                )
                try:
                    self._dbwrapper.execute(alter_query, commit=True)
                except Exception as e:
                    log.info("Unexpected error: %s" % e)

                alter_query = (
                    "DROP TABLE backup_sightings;"
                )
                try:
                    self._dbwrapper.execute(alter_query, commit=True)
                except Exception as e:
                    log.info("Unexpected error: %s" % e)

            if self._version < 4:
                alter_query = (
                    "ALTER TABLE trs_status "
                    "ADD lastPogoReboot varchar(50) NULL DEFAULT NULL"
                )
                column_exist = self._dbwrapper.check_column_exists('trs_status', 'lastPogoReboot')
                if column_exist == 0:
                    try:
                        self._dbwrapper.execute(alter_query, commit=True)
                    except Exception as e:
                        log.info("Unexpected error: %s" % e)

                alter_query = (
                    "ALTER TABLE trs_status "
                    "ADD globalrebootcount int(11) NULL DEFAULT '0'"
                )
                column_exist = self._dbwrapper.check_column_exists('trs_status', 'globalrebootcount')
                if column_exist == 0:
                    try:
                        self._dbwrapper.execute(alter_query, commit=True)
                    except Exception as e:
                        log.info("Unexpected error: %s" % e)

                alter_query = (
                    "ALTER TABLE trs_status "
                    "ADD globalrestartcount int(11) NULL DEFAULT '0'"
                )
                column_exist = self._dbwrapper.check_column_exists('trs_status', 'globalrestartcount')
                if column_exist == 0:
                    try:
                        self._dbwrapper.execute(alter_query, commit=True)
                    except Exception as e:
                        log.info("Unexpected error: %s" % e)

            if self._version < 5:
                alter_query = (
                    "ALTER TABLE trs_status CHANGE lastPogoRestart "
                    "lastPogoRestart VARCHAR(50) NULL DEFAULT NULL"
                )
                try:
                    self._dbwrapper.execute(alter_query, commit=True)
                except Exception as e:
                    log.info("Unexpected error: %s" % e)

            if self._version < 6:
                if self._application_args.db_method == "monocle":
                    alter_query = (
                        "alter table sightings add column costume smallint(6) default 0"
                    )
                    column_exist = self._dbwrapper.check_column_exists('sightings', 'costume')
                    if column_exist == 0:
                        try:
                            self._dbwrapper.execute(alter_query, commit=True)
                        except Exception as e:
                            log.info("Unexpected error: %s" % e)

            if self._version < 7:
                alter_query = (
                    "ALTER TABLE trs_quest "
                    "ADD quest_template VARCHAR(100) NULL DEFAULT NULL "
                    "AFTER quest_reward"
                )
                try:
                    self._dbwrapper.execute(alter_query, commit=True)
                except Exception as e:
                    log.info("Unexpected error: %s" % e)

        self.set_version(current_version)

    def set_version(self, version):
        
        output ={'version': version}
        with open('version.json', 'w') as outfile:  
            json.dump(output, outfile)
