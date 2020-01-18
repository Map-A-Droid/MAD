from collections import OrderedDict
import importlib
import json
import shutil
import sys
from mapadroid.db import DbSchemaUpdater
from mapadroid.utils.logging import logger

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


class MADVersion(object):
    def __init__(self, args, data_manager):
        self._application_args = args
        self.data_manager = data_manager
        self.dbwrapper = self.data_manager.dbc
        self._schema_updater: DbSchemaUpdater = self.dbwrapper.schema_updater
        self._version = 0
        self._madver = list(MAD_UPDATES.keys())[-1]
        self.instance_id = data_manager.instance_id

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
                if not patch.issues:
                    logger.info('Successfully applied patch')
                    self.__set_version(patch_ver)
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

    def get_version(self):
        # checking mappings.json
        self.convert_mappings()
        dbVersion = self.dbwrapper.get_mad_version()
        if not dbVersion:
            logger.warning("Moving internal MAD version to database")
            try:
                with open('version.json') as f:
                    version = json.load(f)
                self._version = int(version['version'])
                self.__set_version(self._version)
            except FileNotFoundError:
                logger.warning("Could not find version.json during move to DB"
                               ", will use version 0")
                self.__set_version(0)
            dbVersion = self.dbwrapper.get_mad_version()
            if dbVersion is not None:
                logger.success("Moved internal MAD version to database "
                               "as version {}", dbVersion)
            else:
                logger.error("Moving internal MAD version to DB failed!")
        else:
            logger.info("Internal MAD version in DB is {}", dbVersion)
            self._version = int(dbVersion)
        if int(self._version) < self._madver:
            logger.warning('Performing updates from version {} to {} now',
                           self._version, self._madver)
            self.start_update()
            logger.success('Updates to version {} finished', self._version)

    def __set_version(self, version):
        self.dbwrapper.update_mad_version(version)
        self._version = version

    def start_update(self):
        if self._madver < self._version:
            logger.error('Mis-matched version number detected.  Not applying any updates')
        else:
            all_patches = list(MAD_UPDATES.keys())
            try:
                last_ver = all_patches.index(self._version)
                first_patch = last_ver + 1
            except ValueError:
                first_patch = 0
            updates_to_apply = all_patches[first_patch:]
            logger.info('Patches to apply: {}', updates_to_apply)
            for patch_ver in updates_to_apply:
                self.__apply_update(patch_ver)
