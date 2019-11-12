import json
import sys

from utils.logging import logger
import shutil
from .convert_mapping import convert_mappings
import re

from db.DbWrapper import DbWrapper
from db.DbSchemaUpdater import DbSchemaUpdater

current_version = 16


class MADVersion(object):

    def __init__(self, args, dbwrapper: DbWrapper):
        self._application_args = args
        self.dbwrapper: DbWrapper = dbwrapper
        self._schema_updater: DbSchemaUpdater = dbwrapper.schema_updater
        self._version = 0

    def get_version(self):
        try:
            # checking mappings.json
            convert_mappings()
            with open('version.json') as f:
                versio = json.load(f)
            self._version = int(versio['version'])
            if int(self._version) < int(current_version):
                logger.success('Performing update now')
                self.start_update()
                logger.success('Updates finished')
        except FileNotFoundError:
            self.set_version(0)
            self.start_update()

    def start_update(self):
        # BACKUP ALL THE THINGS! if we need to update
        if self._version != current_version:
            target = '%s.%s.bk' % (self._application_args.mappings, self._version)
            try:
                shutil.copy(self._application_args.mappings, target)
            except IOError:
                logger.exception('Unable to clone configuration. Exiting')
                sys.exit(1)

        if self._version < 1:
            logger.info('Execute Update for Version 1')
            # Adding quest_reward for PMSF ALT
            if not self._schema_updater.check_column_exists('trs_quest', 'quest_reward'):
                alter_query = (
                    "ALTER TABLE trs_quest "
                    "ADD quest_reward VARCHAR(500) NULL AFTER quest_condition"
                )
                try:
                    self.dbwrapper.execute(alter_query, commit=True)
                except Exception as e:
                    logger.info("Unexpected error: {}", e)

            # Adding quest_task = ingame quest conditions
            if not self._schema_updater.check_column_exists('trs_quest', 'quest_task'):
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
                column_exist = self._schema_updater.check_column_exists(
                    'raid', 'form')
            else:
                logger.error("Invalid db_method in config. Exiting")
                sys.exit(1)

            if not column_exist:
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
            column_exist = self._schema_updater.check_column_exists(
                'trs_status', 'lastPogoReboot')
            if not column_exist:
                try:
                    self.dbwrapper.execute(alter_query, commit=True)
                except Exception as e:
                    logger.info("Unexpected error: {}", e)

            alter_query = (
                "ALTER TABLE trs_status "
                "ADD globalrebootcount int(11) NULL DEFAULT '0'"
            )
            column_exist = self._schema_updater.check_column_exists(
                'trs_status', 'globalrebootcount')
            if not column_exist:
                try:
                    self.dbwrapper.execute(alter_query, commit=True)
                except Exception as e:
                    logger.info("Unexpected error: {}", e)

            alter_query = (
                "ALTER TABLE trs_status "
                "ADD globalrestartcount int(11) NULL DEFAULT '0'"
            )
            column_exist = self._schema_updater.check_column_exists(
                'trs_status', 'globalrestartcount')
            if not column_exist:
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
            column_exist = self._schema_updater.check_column_exists(
                'trs_quest', 'quest_template')
            if not column_exist:
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
            column_exist = self._schema_updater.check_column_exists(
                'trs_stats_detect_raw', 'is_shiny')
            if not column_exist:
                try:
                    self.dbwrapper.execute(query, commit=True)
                except Exception as e:
                    logger.exception("Unexpected error: {}", e)

        if self._version < 12:
            if self._schema_updater.check_index_exists('trs_stats_detect_raw', 'typeworker'):
                query = (
                    "ALTER TABLE trs_stats_detect_raw "
                    "DROP INDEX typeworker, "
                    "ADD INDEX typeworker (worker, type_id)"
                )
            else:
                query = (
                    "ALTER TABLE trs_stats_detect_raw "
                    "ADD INDEX typeworker (worker, type_id)"
                )
            try:
                self.dbwrapper.execute(query, commit=True)
            except Exception as e:
                logger.exception("Unexpected error: {}", e)

            if self._schema_updater.check_index_exists('trs_stats_detect_raw', 'shiny'):
                query = (
                    "ALTER TABLE trs_stats_detect_raw "
                    "DROP INDEX shiny, "
                    "ADD INDEX shiny (is_shiny)"
                )
            else:
                query = (
                    "ALTER TABLE trs_stats_detect_raw "
                    "ADD INDEX shiny (is_shiny)"
                )
            try:
                self.dbwrapper.execute(query, commit=True)
            except Exception as e:
                logger.exception("Unexpected error: {}", e)

        if self._version < 13:
            # Adding current_sleep for worker status
            if not self._schema_updater.check_column_exists('trs_status', 'currentSleepTime'):
                query = (
                    "ALTER TABLE trs_status "
                    "ADD currentSleepTime INT(11) NOT NULL DEFAULT 0"
                )
                try:
                    self.dbwrapper.execute(query, commit=True)
                except Exception as e:
                    logger.exception("Unexpected error: {}", e)

        if self._version < 14:
            update_order = ['monivlist', 'auth', 'devicesettings', 'areas', 'walker', 'devices']
            old_data = {}
            new_data = {}
            cache = {}
            target = '%s.bk' % (self._application_args.mappings,)
            try:
                shutil.copy(self._application_args.mappings, target)
            except IOError:
                logger.exception('Unable to clone configuration. Exiting')
                sys.exit(1)
            with open(self._application_args.mappings, 'rb') as fh:
                old_data = json.load(fh)

            if "migrated" in old_data and old_data["migrated"] is True:
                with open(self._application_args.mappings, 'w') as outfile:
                    json.dump(old_data, outfile, indent=4, sort_keys=True)
            else:
                walkerarea = 'walkerarea'
                walkerarea_ind = 0
                for key in update_order:
                    try:
                        entries = old_data[key]
                    except Exception:
                        entries = []
                    cache[key] = {}
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
                                    entry['settings']['mon_ids_iv'] = '/api/monivlist/%s' % (monlist_ind)
                                    new_data['monivlist']['index'] += 1
                                else:
                                    try:
                                        name = mon_list
                                        uri = '/api/monivlist/%s' % (cache['monivlist'][name])
                                        entry['settings']['mon_ids_iv'] = uri
                                    except Exception:
                                        # No name match.  Maybe an old record so lets toss it
                                        del entry['settings']['mon_ids_iv']
                            except KeyError:
                                # Monlist is not defined for the area
                                pass
                            except Exception:
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
                            if 'pool' in entry:
                                try:
                                    entry['pool'] = '/api/devicesetting/%s' % (cache['devicesettings'][entry['pool']],)
                                except Exception:
                                    if entry['pool'] is not None:
                                        logger.error('DeviceSettings {} is not valid', entry['pool'])
                                    del entry['pool']
                            try:
                                entry['walker'] = '/api/walker/%s' % (cache['walker'][entry['walker']],)
                            except Exception:
                                # The walker no longer exists.  Skip the device
                                continue
                        new_data[key]['entries'][index] = entry
                        index += 1
                    new_data[key]['index'] = index

                new_data['migrated'] = True

                with open(self._application_args.mappings, 'w') as outfile:
                    json.dump(new_data, outfile, indent=4, sort_keys=True)
        if self._version < 15:
            with open(self._application_args.mappings, 'rb') as fh:
                settings = json.load(fh)
            self.__convert_to_id(settings)
            with open(self._application_args.mappings, 'w') as outfile:
                json.dump(settings, outfile, indent=4, sort_keys=True)

        if self._version < 16:
            query = (
                "CREATE TABLE IF NOT EXISTS `trs_visited` ("
                "`pokestop_id` varchar(50) NOT NULL collate utf8mb4_unicode_ci,"
                "`origin` varchar(50) NOT NULL collate utf8mb4_unicode_ci,"
                "PRIMARY KEY (`pokestop_id`,`origin`)"
                ")"
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

    def __convert_to_id(self, data):
        regex = re.compile(r'/api/.*/\d+')
        for key, val in data.items():
            if type(val) is dict:
                data[key] = self.__convert_to_id(val)
            elif type(val) is list:
                valid = []
                for elem in val:
                    if type(elem) is str:
                        valid.append(elem[elem.rfind('/')+1:])
                    else:
                        valid.append(elem)
                data[key] = valid
            elif type(val) is str and regex.search(val):
                data[key] = val[val.rfind('/')+1:]
        return data
