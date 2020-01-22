from collections import OrderedDict
import importlib
import json
import shutil
import sys
from mapadroid.db import DbSchemaUpdater
from mapadroid.utils.logging import logger
import mysql.connector

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
    (19, 'patch_19'),
    (20, 'patch_20'),
    (21, 'patch_21'),
    (22, 'patch_22'),
    (23, 'patch_23'),
])


class MADPatcher(object):
    def __init__(self, args, data_manager):
        self._application_args = args
        self.data_manager = data_manager
        self.dbwrapper = self.data_manager.dbc
        self._schema_updater: DbSchemaUpdater = self.dbwrapper.schema_updater
        self._madver = list(MAD_UPDATES.keys())[-1]
        self.__get_installed_version()
        self.instance_id = data_manager.instance_id
        if self.__update_required():
            self.__update_mad()

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
                    logger.info('Successfully applied patch')
                else:
                    logger.error('Patch was unsuccessful.  Exiting')
                    sys.exit(1)
            except Exception:
                logger.opt(exception=True).error('Patch was unsuccessful.  Exiting')
                sys.exit(1)

    def convert_mappings(self):
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
        # checking mappings.json
        self.convert_mappings()
        try:
            self._installed_ver = self.dbwrapper.get_mad_version()
        except mysql.connector.Error as err:
            # This would be a lot easier with transactions
            try:
                with open('scripts/SQL/rocketmap.sql') as fh:
                    tables = "".join(fh.readlines()).split(";")
                    for table in tables:
                        install_cmd = '%s;%s;%s'
                        args = ('SET FOREIGN_KEY_CHECKS=0', 'SET NAMES utf8mb4', table)
                        self.dbwrapper.execute(install_cmd % args, commit=True)
                self.instance_id = self.dbwrapper.get_instance_id()
                self.data_manager.instance_id = self.instance_id
                self.__set_installed_ver(self._madver)
                logger.success('Successfully installed MAD schema to the database')
            except:
                logger.critical('Unable to install default MAD schema.  Please install the schema from '
                                'scripts/SQL/rocketmap.sql')
                sys.exit(1)
        if not self._installed_ver:
            logger.warning("Moving internal MAD version to database")
            try:
                with open('version.json') as f:
                    version = json.load(f)
                self._installed_ver = int(version['version'])
                self.__set_installed_ver(self._installed_ver)
            except FileNotFoundError:
                logger.warning("Could not find version.json during move to DB"
                               ", will use version 0")
                self.__set_installed_ver(0)
            self._installed_ver = self.dbwrapper.get_mad_version()
            if self._installed_ver is not None:
                logger.success("Moved internal MAD version to database "
                               "as version {}", self._installed_ver)
            else:
                logger.error("Moving internal MAD version to DB failed!")
        else:
            logger.info("Internal MAD version in DB is {}", self._installed_ver)

    def __set_installed_ver(self, version):
        self.dbwrapper.update_mad_version(version)
        self._installed_ver = version

    def __update_mad(self):
        if self._madver < self._installed_ver:
            logger.error('Mis-matched version number detected.  Not applying any updates')
        else:
            logger.warning('Performing updates from version {} to {} now',
                           self._installed_ver, self._madver)
            self.__update_mad()
            all_patches = list(MAD_UPDATES.keys())
            try:
                last_ver = all_patches.index(self._installed_ver)
                first_patch = last_ver + 1
            except ValueError:
                first_patch = 0
            updates_to_apply = all_patches[first_patch:]
            logger.info('Patches to apply: {}', updates_to_apply)
            for patch_ver in updates_to_apply:
                self.__apply_update(patch_ver)
            logger.success('Updates to version {} finished', self._installed_ver)

    def __update_required(self):
        if self._installed_ver == 0:
            sql = "SELECT COUNT(*) FROM `information_schema`.`views` WHERE `TABLE_NAME` = 'v_trs_status'"
            count = self.dbwrapper.autofetch_value(sql)
            if count:
                logger.success('It looks like the database has been successfully installed.  Setting version to {}',
                               self._madver)
                self.__set_installed_ver(self._madver)
                return False
            else:
                return True
        else:
            self._schema_updater.ensure_unversioned_tables_exist()
            self._schema_updater.ensure_unversioned_columns_exist()
            self._schema_updater.create_madmin_databases_if_not_exists()
            self._schema_updater.ensure_unversioned_madmin_columns_exist()
            return self._installed_ver < self._madver
