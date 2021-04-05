import importlib
import json
import os
import shutil
import sys
from collections import OrderedDict

import mysql.connector

from mapadroid.db import DbSchemaUpdater
from mapadroid.utils.logging import LoggerEnums, get_logger

logger = get_logger(LoggerEnums.patcher)

# OrderedDict containing all required updates with their filename reference.  The dict is stored as (version, filename)
MAD_UPDATES = OrderedDict([
    (1, 'patch_1'),
    (2, 'patch_2'),
    (7, 'patch_7'),
    (8, 'patch_8'),
    (9, 'patch_9'),
    (10, 'patch_10'),
    (11, 'patch_11'),
    (12, 'patch_12'),
    (13, 'patch_13'),
    (14, 'patch_14'),
    (15, 'patch_15'),
    (16, 'patch_16'),
    (17, 'patch_17'),
    (18, 'patch_18'),
    (21, 'patch_21'),
    (23, 'patch_23'),
    (24, 'patch_24'),
    (25, 'patch_25'),
    (26, 'patch_26'),
    (27, 'patch_27'),
    (28, 'patch_28'),
    (29, 'patch_29'),
    (30, 'patch_30'),
    (31, 'trs_status_lastProtoDateTime_fix'),
    (32, 'reset_routecalc_algo'),
    (33, 'routecalc_rename'),
    (34, 'trs_stats_detect_raw_split'),
    (35, 'madrom_autoconfig'),
    (36, 'pokemon_iv_index'),
    (37, 'move_ptc_accounts'),
    (38, 'remove_hatch_delay'),
    (39, 'extend_trs_quest_pogodroid_190'),
    (40, 'add_is_ar_scan_eligible'),
    (41, 'dynamic_iv_list'),
    (42, 'add_encounter_all'),
    (43, 'remove_tap_duration')
])


class MADPatcher(object):
    def __init__(self, args, data_manager):
        self._application_args = args
        self.data_manager = data_manager
        self.dbwrapper = self.data_manager.dbc
        self._schema_updater: DbSchemaUpdater = self.dbwrapper.schema_updater
        self._madver = list(MAD_UPDATES.keys())[-1]
        self._installed_ver = None
        self.__validate_versions_schema()
        # If the versions table does not exist we have to install the schema.  When the schema is set, we are then on
        # the latest table so none of these checks are required
        if self._installed_ver is None:
            self.__convert_mappings()
            self.__get_installed_version()
            if self._installed_ver in [23, 24]:
                self.__validate_trs_schema()
            self._schema_updater.ensure_unversioned_tables_exist()
            self._schema_updater.ensure_unversioned_columns_exist()
            self._schema_updater.create_madmin_databases_if_not_exists()
            self._schema_updater.ensure_unversioned_madmin_columns_exist()
            if self.__update_required():
                self.__update_mad()
            else:
                logger.success('MAD DB is running latest version')

    def __apply_update(self, patch_ver):
        filename = MAD_UPDATES[patch_ver]
        patch_name = 'mapadroid.patcher.%s' % filename
        try:
            patch_base = importlib.import_module(patch_name)
        except ImportError:
            logger.opt(exception=True).error('Unable to import patch {}.  Exiting', patch_name)
            sys.exit(1)
        else:
            # Execute the patch and catch any errors for logging
            try:
                patch = patch_base.Patch(logger, self.dbwrapper, self.data_manager, self._application_args)
                if patch.completed and not patch.issues:
                    self.__set_installed_ver(patch_ver)
                    logger.success('Successfully applied patch')
                else:
                    logger.fatal('Patch was unsuccessful.  Exiting')
                    sys.exit(1)
            except Exception:
                logger.opt(exception=True).error('Patch was unsuccessful.  Exiting')
                sys.exit(1)

    def __convert_mappings(self):
        mapping_file = self._application_args.mappings
        save_mapping_file = self._application_args.mappings.replace('.json', '_org.json')
        try:
            with open(mapping_file) as f:
                __raw_json = json.load(f)
            walker = []
            walkersetup = []
            if "walker" not in __raw_json:
                logger.info("Unconverted mapping file found")
                logger.info("Saving current file")
                shutil.copy(mapping_file, save_mapping_file)
                __raw_json['walker'] = []
                count = 0
                walker = []
                exist = {}
                for dev in __raw_json['devices']:
                    logger.info("Converting device {}", str(dev['origin']))
                    walkersetup = []
                    daytime_area = dev.get('daytime_area', False)
                    nightime_area = dev.get('nighttime_area', False)
                    walkername = str(daytime_area)
                    timer_invert = ""
                    if nightime_area:
                        if (dev.get('switch', False)):
                            timer_old = dev.get('switch_interval', "['0:00','23:59']")
                            walkername = walkername + '-' + str(nightime_area)
                            timer_normal = str(timer_old[0]) + '-' + str(timer_old[1])
                            timer_invert = str(timer_old[1]) + '-' + str(timer_old[0])
                            del __raw_json['devices'][count]['switch_interval']
                            del __raw_json['devices'][count]['switch']
                    if len(timer_invert) > 0:
                        walkersetup.append(
                            {'walkerarea': daytime_area, "walkertype": "period", "walkervalue": timer_invert})
                        walkersetup.append(
                            {'walkerarea': nightime_area, "walkertype": "period", "walkervalue": timer_normal})
                    else:
                        walkersetup.append(
                            {'walkerarea': daytime_area, "walkertype": "coords", "walkervalue": ""})
                    if walkername not in exist:
                        walker.append({'walkername': walkername, "setup": walkersetup})
                        exist[walkername] = True
                    del __raw_json['devices'][count]['daytime_area']
                    del __raw_json['devices'][count]['nighttime_area']
                    __raw_json['devices'][count]['walker'] = str(walkername)
                    count += 1
                __raw_json['walker'] = walker
                with open(mapping_file, 'w') as outfile:
                    json.dump(__raw_json, outfile, indent=4, sort_keys=True)
                    logger.info('Finished converting mapping file')
        except IOError:
            pass
        except Exception:
            logger.exception('Unknown issue during migration. Exiting')
            sys.exit(1)

    def __get_installed_version(self):
        try:
            self._installed_ver = self.dbwrapper.get_mad_version()
            if self._installed_ver:
                logger.info("Internal MAD version in DB is {}", self._installed_ver)
            else:
                logger.info('Partial schema detected.  Additional steps required')
                self.__install_instance_table()
                # Attempt to read the old version.json file to get the latest install version in the database
                try:
                    with open('version.json') as f:
                        self._installed_ver = json.load(f)['version']
                    logger.success("Moving internal MAD version to database")
                    self.__set_installed_ver(self._installed_ver)
                except FileNotFoundError:
                    logger.info('New installation detected with a partial schema detected.  Updates will be attempted')
                    self._installed_ver = 0
                    self.__set_installed_ver(self._installed_ver)
                reload_instance_id(self.data_manager)
                logger.success("Moved internal MAD version to database as version {}", self._installed_ver)
        except Exception:
            logger.opt(exception=True).critical('Unknown exception occurred during getting the MAD DB version.'
                                                '  Exiting')

    def __install_instance_table(self):
        sql = "CREATE TABLE `madmin_instance` (\n"\
              "`instance_id` int(10) unsigned NOT NULL AUTO_INCREMENT,\n"\
              "`name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,\n"\
              "PRIMARY KEY (`instance_id`),\n"\
              "UNIQUE KEY `name` (`name`)\n"\
              ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;"
        self.dbwrapper.execute(sql, commit=True, suppress_log=True)

    def __add_default_event(self):
        sql = "INSERT IGNORE into `trs_event` " \
              "(`id`, `event_name`, `event_start`, `event_end`, `event_lure_duration`) values " \
              "('1', 'DEFAULT', '1970-01-01', '2099-12-31', 30)"
        self.dbwrapper.execute(sql, commit=True, suppress_log=True)

    def __install_schema(self):
        try:
            sql_file = ["scripts", "SQL", "rocketmap.sql"]
            with open(os.path.join(sql_file), "r") as fh:
                tables = "".join(fh.readlines()).split(";")
                for table in tables:
                    install_cmd = '%s;%s;%s'
                    args = ('SET FOREIGN_KEY_CHECKS=0', 'SET NAMES utf8mb4', table)
                    self.dbwrapper.execute(install_cmd % args, commit=True)
            self.__set_installed_ver(self._madver)
            logger.success('Successfully installed MAD version {} to the database', self._installed_ver)
            self.__add_default_event()
            reload_instance_id(self.data_manager)
        except Exception:
            logger.opt(exception=True).critical('Unable to install default MAD schema.  Please install the schema from '
                                                'scripts/SQL/rocketmap.sql')
            sys.exit(1)

    def __set_installed_ver(self, version):
        self._installed_ver = version
        self.dbwrapper.update_mad_version(version)

    def __update_mad(self):
        if self._madver < self._installed_ver:
            logger.error('Mis-matched version number detected.  Not applying any updates')
        else:
            logger.warning('Performing updates from version {} to {} now',
                           self._installed_ver, self._madver)
            all_patches = list(MAD_UPDATES.keys())
            try:
                last_ver = all_patches.index(self._installed_ver)
                first_patch = last_ver + 1
            except ValueError:
                # The current version of the patch was most likely removed as it was no longer needed.  Determine
                # where to start by finding the last executed
                next_patch = None
                for patch_ver in all_patches:
                    if self._installed_ver > patch_ver:
                        continue
                    next_patch = patch_ver
                    break
                try:
                    first_patch = all_patches.index(next_patch)
                except ValueError:
                    logger.critical('Unable to find the next patch to apply')
            updates_to_apply = all_patches[first_patch:]
            logger.info('Patches to apply: {}', updates_to_apply)
            for patch_ver in updates_to_apply:
                self.__apply_update(patch_ver)
            logger.success('Updates to version {} finished', self._installed_ver)

    def __update_required(self):
        return self._installed_ver < self._madver

    def __update_versions_table(self):
        sql = "ALTER TABLE `versions` ADD PRIMARY KEY(`key`)"
        self.dbwrapper.execute(sql, commit=True, suppress_log=True, raise_exc=True)

    def __validate_trs_schema(self):
        point_fields = ['currentPos', 'lastPos']
        bool_fields = ['rebootingOption', 'init']
        sql = "SHOW FIELDS FROM `trs_status`"
        fields = self.dbwrapper.autofetch_all(sql)
        field_defs = {}
        for field in fields:
            field_name = field['Field']
            field_defs[field_name] = field
        sql = "SELECT %s FROM `trs_status`" % (','.join(field_defs.keys()),)
        if 'device_id' not in field_defs.keys() or 'instance_id' not in field_defs.keys():
            logger.info('Invalid schema detected on trs_status.  Rolling back to 22')
            self._installed_ver = 22
        for field in point_fields:
            if field_defs[field]['Type'] == 'point':
                continue
            self._installed_ver = 22
        for field in bool_fields:
            if field_defs[field]['Type'] == 'tinyint(1)':
                continue
            self._installed_ver = 22

    def __validate_versions_schema(self):
        """ Verify status of the versions table

            Validate the PK exists for the version table.  If it does not, attempt to create it.  If we run into
            duplicate keys, de-dupe the table then apply the PK
        """
        try:
            sql = "SHOW FIELDS FROM `versions`"
            columns = self.dbwrapper.autofetch_all(sql, suppress_log=True)
        except mysql.connector.Error:
            # Version table does not exist.  This is installed with the base install so we can assume the required
            # tables have not been created
            install_schema(self.dbwrapper)
            add_default_event(self.dbwrapper)
            reload_instance_id(self.data_manager)
        else:
            for column in columns:
                if column['Field'] != 'key':
                    continue
                if column['Key'] != 'PRI':
                    logger.info('Primary key not configured on the versions table.  Applying fix')
                    try:
                        self.__update_versions_table()
                    except mysql.connector.Error as err:
                        if err.errno == 1062:
                            logger.info('Multiple versions detected in the table.  Performing maintenance on the table')
                            sql = "SELECT `key`, MAX(`val`) AS 'val' FROM `versions`"
                            max_vers = self.dbwrapper.autofetch_all(sql)
                            logger.info('Versions: {}', max_vers)
                            sql = "DELETE FROM `versions`"
                            self.dbwrapper.execute(sql, commit=True)
                            for elem in max_vers:
                                self.dbwrapper.autoexec_insert('versions', elem)
                            logger.success('Successfully de-duplicated versions table and set each key to the '
                                           'maximum value from the table')
                            self.__update_versions_table()


def install_schema(dbwrapper):
    try:
        sql_file = ["scripts", "SQL", "rocketmap.sql"]
        with open(os.path.join(*sql_file), "r") as fh:
            tables = "".join(fh.readlines()).split(";")
            for table in tables:
                install_cmd = '%s;%s;%s'
                args = ('SET FOREIGN_KEY_CHECKS=0', 'SET NAMES utf8mb4', table)
                dbwrapper.execute(install_cmd % args, commit=True)
        version = list(MAD_UPDATES.keys())[-1]
        dbwrapper.update_mad_version(version)
        logger.success('Successfully installed MAD version {} to the database', version)
        add_default_event(dbwrapper)
    except Exception:
        logger.opt(exception=True).critical('Unable to install default MAD schema.  Please install the schema from '
                                            'scripts/SQL/rocketmap.sql')
        sys.exit(1)


def add_default_event(dbwrapper):
    sql = "INSERT IGNORE into `trs_event` " \
          "(`id`, `event_name`, `event_start`, `event_end`, `event_lure_duration`) values " \
          "('1', 'DEFAULT', '1970-01-01', '2099-12-31', 30)"
    dbwrapper.execute(sql, commit=True, suppress_log=True)


def reload_instance_id(data_manager):
    data_manager.dbc.get_instance_id()
    data_manager.instance_id = data_manager.dbc.instance_id
