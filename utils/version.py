import json
import sys

from utils.logging import logger
import shutil
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

            # Adding form column for rm / monocle if not exists
            if self._application_args.db_method == "rm":
                alter_query = (
                    "ALTER TABLE raid "
                    "ADD form smallint(6) DEFAULT NULL"
                )
                column_exist = self.dbwrapper.check_column_exists(
                    'raid', 'form')
            elif self._application_args.db_method == "monocle":
                alter_query = (
                    "ALTER TABLE raids "
                    "ADD form smallint(6) DEFAULT NULL"
                )
                column_exist = self.dbwrapper.check_column_exists(
                    'raids', 'form')
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
        if self._version < 3:
            if self._application_args.db_method == "monocle":
                # Add Weather Index
                alter_query = (
                    "ALTER TABLE weather ADD UNIQUE s2_cell_id (s2_cell_id) USING BTREE"
                )
                try:
                    self.dbwrapper.execute(alter_query, commit=True)
                except Exception as e:
                    logger.info("Unexpected error: {}", e)

                # Change Mon Unique Index
                alter_query = (
                    "ALTER TABLE sightings DROP INDEX timestamp_encounter_id_unique"
                )
                try:
                    self.dbwrapper.execute(alter_query, commit=True)
                except Exception as e:
                    logger.info("Unexpected error: {}", e)

                alter_query = (
                    "ALTER TABLE sightings DROP INDEX encounter_id;"
                )
                try:
                    self.dbwrapper.execute(alter_query, commit=True)
                except Exception as e:
                    logger.info("Unexpected error: {}", e)

                alter_query = (
                    "CREATE TABLE sightings_temp LIKE sightings;"
                )
                try:
                    self.dbwrapper.execute(alter_query, commit=True)
                except Exception as e:
                    logger.info("Unexpected error: {}", e)

                alter_query = (
                    "ALTER TABLE sightings_temp ADD UNIQUE(encounter_id);"
                )
                try:
                    self.dbwrapper.execute(alter_query, commit=True)
                except Exception as e:
                    logger.info("Unexpected error: {}", e)

                alter_query = (
                    "INSERT IGNORE INTO sightings_temp SELECT * FROM sightings ORDER BY id;"
                )
                try:
                    self.dbwrapper.execute(alter_query, commit=True)
                except Exception as e:
                    logger.info("Unexpected error: {}", e)

                alter_query = (
                    "RENAME TABLE sightings TO backup_sightings, sightings_temp TO sightings;"
                )
                try:
                    self.dbwrapper.execute(alter_query, commit=True)
                except Exception as e:
                    logger.info("Unexpected error: {}", e)

                alter_query = (
                    "DROP TABLE backup_sightings;"
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

            if self._application_args.db_method == "monocle":
                alter_query = (
                    "alter table sightings add column costume smallint(6) default 0"
                )
                column_exist = self.dbwrapper.check_column_exists(
                    'sightings', 'costume')
                if column_exist == 0:
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
            try:
                self.dbwrapper.execute(query, commit=True)
            except Exception as e:
                logger.exception("Unexpected error: {}", e)

        if self._version < 12:
            query = (
                "ALTER TABLE trs_stats_detect_raw DROP INDEX IF EXISTS typeworker, "
                "ADD INDEX typeworker (worker, type_id)"
            )
            try:
                self.dbwrapper.execute(query, commit=True)
            except Exception as e:
                logger.exception("Unexpected error: {}", e)

            query = (
                "ALTER TABLE trs_stats_detect_raw DROP INDEX IF EXISTS shiny, "
                "ADD INDEX shiny (is_shiny)"
            )
            try:
                self.dbwrapper.execute(query, commit=True)
            except Exception as e:
                logger.exception("Unexpected error: {}", e)
        if self._version < 13:
            update_order = ['monivlist', 'auth', 'devicesettings', 'areas', 'walker', 'devices']
            old_data = {}
            new_data = {}
            cache = {}
            target = '%s.bk' % (self._application_args.mappings,)
            try:
                shutil.copy(self._application_args.mappings, target)
            except IOError as e:
                print('Unable to clone configuration.  Exiting')
                sys.exit(1)
            with open(self._application_args.mappings, 'rb') as fh:
                old_data = json.load(fh)
            walkerarea = 'walkerarea'
            walkerarea_ind = 0
            for key in update_order:
                try:
                    entries = old_data[key]
                except:
                    entries = []
                cache[key] = {}
                if type(entries) is dict:
                    continue
                index = 0
                new_data[key] = {
                    'index': index,
                    'entries': {}
                }
                if key == 'walker':
                    new_data[walkerarea] = {
                        'index': index,
                        'entries': {}
                    }
                for entry in entries:
                    if key == 'monivlist':
                        cache[key][entry['monlist']] = index
                    if key == 'devicesettings':
                        cache[key][entry['devicepool']] = index
                    elif key == 'areas':
                        cache[key][entry['name']] = index
                        try:
                            mon_list = entry['settings']['mon_ids_iv']
                            if type(mon_list) is list:
                                monlist_ind = new_data['monivlist']['index']
                                new_data['monivlist']['entries'][index] = {
                                    'monlist': 'Update List',
                                    'mon_ids_iv': mon_list
                                }
                                entry['settings']['mon_ids_iv'] = '/api/monlist/%s' % (monlist_ind)
                                new_data['monivlist']['index'] += 1
                            else:
                                try:
                                    name = mon_list
                                    uri = '/api/monlist/%s' % (cache['monivlist'][name])
                                    entry['settings']['mon_ids_iv'] = uri
                                except:
                                    # No name match.  Maybe an old record so lets toss it
                                    del entry['settings']['mon_ids_iv']
                        except KeyError:
                            pass
                        except:
                            # No monlist specified
                            pass
                    elif key == 'walker':
                        cache[key][entry['walkername']] = index
                        valid_areas = []
                        if 'setup' in entry:
                            for ind, area in enumerate(entry['setup']):
                                try:
                                    area['walkerarea'] = '/api/area/%s' % (cache['areas'][area['walkerarea']],)
                                except KeyError:
                                    # The area no longer exists.  Remove from the path
                                    pass
                                else:
                                    new_data[walkerarea]['entries'][walkerarea_ind] = area
                                    valid_areas.append('/api/walkerarea/%s' % walkerarea_ind)
                                    walkerarea_ind += 1
                            entry['setup'] = valid_areas
                            new_data[walkerarea]['index'] = walkerarea_ind
                        else:
                            entry['setup'] = []
                    elif key == 'devices':
                        try:
                            entry['pool'] = '/api/devicesetting/%s' % (cache['devicesettings'][entry['pool']],)
                        except:
                            # The pool no longer exists.  Skip the device
                            continue
                        try:
                            entry['walker'] = '/api/walker/%s' % (cache['walker'][entry['walker']],)
                        except:
                            # The walker no longer exists.  Skip the device
                            continue
                    new_data[key]['entries'][index] = entry
                    index += 1
                new_data[key]['index'] = index
            with open(self._application_args.mappings, 'w') as outfile:
                json.dump(new_data, outfile, indent=4, sort_keys=True)

        self.set_version(current_version)

    def set_version(self, version):
        output = {'version': version}
        with open('version.json', 'w') as outfile:
            json.dump(output, outfile)

