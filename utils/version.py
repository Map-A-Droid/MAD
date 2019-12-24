import json
import sys

from utils.logging import logger
import shutil
from .convert_mapping import convert_mappings
import re
import utils.data_manager
from pathlib import Path
import os
import copy
from db.DbWrapper import DbWrapper
from db.DbSchemaUpdater import DbSchemaUpdater

current_version = 19

class MADVersion(object):

    def __init__(self, args, data_manager):
        self._application_args = args
        self.data_manager = data_manager
        self.dbwrapper = self.data_manager.dbc
        self._schema_updater: DbSchemaUpdater = self.dbwrapper.schema_updater
        self._version = 0
        self.instance_id = data_manager.instance_id

    def get_version(self):
        try:
            # checking mappings.json
            convert_mappings()
            with open('version.json') as f:
                version = json.load(f)
            self._version = int(version['version'])
            if int(self._version) < int(current_version):
                logger.success('Performing update now')
                self.start_update()
                logger.success('Updates finished')
        except FileNotFoundError:
            self.set_version(0)
            self.start_update()

    def start_update(self):
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
            try:
                target = '%s.bk' % (self._application_args.mappings,)
                shutil.copy(self._application_args.mappings, target)
                with open(self._application_args.mappings, 'rb') as fh:
                    old_data = json.load(fh)
                if ("migrated" in old_data and old_data["migrated"] is True):
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
            except IOError:
                pass
            except Exception as err:
                logger.exception('Unknown issue during migration. Exiting')
                sys.exit(1)
        if self._version < 15:
            try:
                with open(self._application_args.mappings, 'rb') as fh:
                    settings = json.load(fh)
                self.__convert_to_id(settings)
                with open(self._application_args.mappings, 'w') as outfile:
                    json.dump(settings, outfile, indent=4, sort_keys=True)
            except IOError:
                pass
            except Exception as err:
                logger.exception('Unknown issue during migration. Exiting')
                sys.exit(1)
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

        if self._version < 17:
            try:
                # Goodbye mappings.json, it was nice knowing ya!
                update_order = ['monivlist', 'auth', 'devicesettings', 'areas', 'walkerarea', 'walker', 'devices']
                with open(self._application_args.mappings, 'rb') as fh:
                    config_file = json.load(fh)
                geofences = {}
                routecalcs = {}
                conversion_issues = []
                # A wonderful decision that I made was to start at ID 0 on the previous conversion which causes an issue
                # with primary keys in MySQL / MariaDB.  Make the required changes to ID's and save the file in-case the
                # conversion is re-run.  We do not want dupe data in the database
                cache = {}
                for section in update_order:
                    for elem_id, elem in config_file[section]['entries'].items():
                        if section == 'areas':
                            try:
                                if int(elem['settings']['mon_ids_iv']) == 0:
                                    elem['settings']['mon_ids_iv'] = cache['monivlist']
                            except KeyError:
                                pass
                        elif section == 'devices':
                            if int(elem['walker']) == 0:
                                elem['walker'] = cache['walker']
                            if 'pool' in elem and elem['pool'] is not None and int(elem['pool']) == 0:
                                elem['pool'] = cache['devicesettings']
                        elif section == 'walkerarea':
                            if int(elem['walkerarea']) == 0:
                                elem['walkerarea'] = cache['areas']
                        elif section == 'walker':
                            setup = []
                            for walkerarea_id in elem['setup']:
                                if int(walkerarea_id) != 0:
                                    setup.append(walkerarea_id)
                                    continue
                                setup.append(cache['walkerarea'])
                            elem['setup'] = setup
                    entry = None
                    try:
                        entry = config_file[section]['entries']["0"]
                    except KeyError:
                        continue
                    cache[section] = str(config_file[section]['index'])
                    config_file[section]['entries'][cache[section]] = entry
                    del config_file[section]['entries']["0"]
                    config_file[section]['index'] += 1
                if cache:
                    logger.info('One or more resources with ID 0 found.  Converting them off 0 and updating the '\
                                'mappings.json file.  {}', cache)
                    with open(self._application_args.mappings, 'w') as outfile:
                        json.dump(config_file, outfile, indent=4, sort_keys=True)
                # For multi-instance we do not want to re-use IDs.  If and ID is reused we need to adjust it and all
                # foreign keys
                generate_new_ids = {}
                for section in update_order:
                    dm_section = section
                    if section == 'areas':
                        dm_section = 'area'
                    elif section == 'devices':
                        dm_section = 'device'
                    elif section == 'devicesettings':
                        dm_section = 'devicepool'
                    for elem_id, elem in config_file[section]['entries'].items():
                        try:
                            mode = elem['mode']
                        except:
                            mode = None
                        resource_def = self.data_manager.get_resource_def(dm_section, mode=mode)
                        sql = "SELECT `%s` FROM `%s` WHERE `%s` = %%s AND `instance_id` != %%s"
                        sql_args = (resource_def.primary_key, resource_def.table, resource_def.primary_key)
                        sql_format_args = (elem_id, self.data_manager.instance_id)
                        exists = self.dbwrapper.autofetch_value(sql % sql_args, args=sql_format_args)
                        if not exists:
                            continue
                        logger.info('{} {} already exists and a new ID will be generated', dm_section, elem_id)
                        if dm_section not in generate_new_ids:
                            generate_new_ids[dm_section] = {}
                        generate_new_ids[dm_section][elem_id] = None
                # Load the elements into their resources and save to DB
                for section in update_order:
                    dm_section = section
                    if section == 'areas':
                        dm_section = 'area'
                    elif section == 'devices':
                        dm_section = 'device'
                    elif section == 'devicesettings':
                        dm_section = 'devicepool'
                    for key, elem in copy.deepcopy(config_file[section]['entries']).items():
                        save_elem = copy.deepcopy(elem)
                        logger.debug('Converting {} {}', section, key)
                        tmp_mode = None
                        if section == 'areas':
                            mode = elem['mode']
                            tmp_mode = mode
                            del elem['mode']
                            resource = utils.data_manager.modules.MAPPINGS['area'](self.data_manager, mode=mode)
                            geofence_sections = ['geofence_included', 'geofence_excluded']
                            for geofence_section in geofence_sections:
                                try:
                                    geofence = elem[geofence_section]
                                    if type(geofence) is int:
                                        continue
                                    if geofence and geofence not in geofences:
                                        try:
                                            geo_id = self.__convert_geofence(geofence)
                                            geofences[geofence] = geo_id
                                            elem[geofence_section] = geofences[geofence]
                                        except utils.data_manager.dm_exceptions.UpdateIssue as err:
                                            conversion_issues.append((section, elem_id, err.issues))
                                    else:
                                        elem[geofence_section] = geofences[geofence]
                                except KeyError:
                                    pass
                            route = '%s.calc' % (elem['routecalc'],)
                            if type(elem['routecalc']) is str:
                                if route not in routecalcs:
                                    route_path = os.path.join(self._application_args.file_path, route)
                                    route_resource = self.data_manager.get_resource('routecalc')
                                    stripped_data = []
                                    try:
                                        with open(route_path, 'rb') as fh:
                                            for line in fh:
                                                stripped = line.strip()
                                                if type(stripped) != str:
                                                    stripped = stripped.decode('utf-8')
                                                stripped_data.append(stripped)
                                    except IOError as err:
                                        conversion_issues.append((section, elem_id, err))
                                        logger.warning('Unable to open %s.  Using empty route' % (route))
                                    route_resource['routefile'] = stripped_data
                                    route_resource.save(force_insert=True)
                                    routecalcs[route] = route_resource.identifier
                                if route in routecalcs:
                                    elem['routecalc'] = routecalcs[route]
                        else:
                            resource = utils.data_manager.modules.MAPPINGS[dm_section](self.data_manager)
                        # Settings made it into some configs where it should not be.  lets clear those out now
                        if 'settings' in elem and 'settings' not in resource.configuration:
                            del elem['settings']
                        # Update any IDs that have been converted.  There are no required updates for monivlist, auth,
                        # or devicesettings as they are not dependent on other resources
                        # ['monivlist', 'auth', 'devicesettings', 'areas', 'walkerarea', 'walker', 'devices']
                        if dm_section == 'area':
                            try:
                                monlist = elem['settings']['mon_ids_iv']
                                elem['settings']['mon_ids_iv'] = generate_new_ids['monivlist'][monlist]
                                save_elem['settings']['mon_ids_iv'] = str(generate_new_ids['monivlist'][monlist])
                                logger.info('Updating monivlist to area {} to {}', key, elem['settings']['mon_ids_iv'])
                            except KeyError:
                                pass
                        elif dm_section == 'device':
                            try:
                                pool_id = elem['pool']
                                elem['pool'] = generate_new_ids['devicepool'][pool_id]
                                save_elem['pool'] = str(generate_new_ids['devicepool'][pool_id])
                                logger.info('Updating device pool from {} to {}', pool_id, elem['pool'])
                            except KeyError:
                                pass
                            try:
                                walker_id = elem['walker']
                                elem['walker'] = generate_new_ids['walker'][walker_id]
                                save_elem['walker'] = str(generate_new_ids['walker'][walker_id])
                                logger.info('Updating device walker from {} to {}', pool_id, elem['walker'])
                            except KeyError:
                                pass
                        elif dm_section == 'walker':
                            new_list = []
                            for walkerarea_id in elem['setup']:
                                try:
                                    new_list.append(str(generate_new_ids['walkerarea'][walkerarea_id]))
                                    logger.info('Updating walker-walkerarea {} to {}', walkerarea_id, new_list[-1])
                                except KeyError:
                                    new_list.append(walkerarea_id)
                            elem['setup'] = new_list
                            save_elem['setup'] = new_list
                        elif dm_section == 'walkerarea':
                            try:
                                area_id = elem['walkerarea']
                                elem['walkerarea'] = generate_new_ids['area'][area_id]
                                save_elem['walkerarea'] = str(generate_new_ids['area'][area_id])
                                logger.info('Updating walkerarea from {} to {}', area_id, elem['walkerarea'])
                            except KeyError:
                                pass
                        save_new_id = False
                        try:
                            generate_new_ids[dm_section][key]
                            save_new_id = True
                        except:
                            resource.identifier = key
                        resource.update(elem)
                        try:
                            resource.save(force_insert=True, ignore_issues=['unknown'])
                        except utils.data_manager.dm_exceptions.UpdateIssue as err:
                            conversion_issues.append((section, key, err.issues))
                        except Exception as err:
                            conversion_issues.append((section, key, err))
                        else:
                            if save_new_id:
                                generate_new_ids[dm_section][key] = resource.identifier
                                config_file[section]['entries'][str(resource.identifier)] = save_elem
                                del config_file[section]['entries'][key]
                                if resource.identifier >= int(config_file[section]['index']):
                                    config_file[section]['index'] = resource.identifier + 1
                if conversion_issues:
                    logger.error('The configuration was not partially moved to the database.  The following resources '\
                                 'were not converted.')
                    for (section, identifier, issue) in conversion_issues:
                        logger.error('{} {}: {}', section, identifier, issue)
                if generate_new_ids:
                    with open(self._application_args.mappings, 'w') as outfile:
                        json.dump(config_file, outfile, indent=4, sort_keys=True)
            except IOError:
                pass
            except Exception as err:
                logger.exception('Unknown issue during migration. Exiting')
                sys.exit(1)
        if self._version < 18:
            query = (
                "ALTER TABLE `trs_status` CHANGE `instance` `instance` VARCHAR(50) CHARACTER "
                "SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL;"
            )
            try:
                self.dbwrapper.execute(query, commit=True)
            except Exception as e:
                logger.exception("Unexpected error: {}", e)
        if self._version < 19:
            # Non-instanced devices in trs_status will cause the upgrade to fail.  Since these entries are prior
            # to bfbadcd we can remove them
            sql = "SELECT `origin` FROM `trs_status` WHERE `instance` = ''"
            bad_devs = self.dbwrapper.autofetch_column(sql)
            if bad_devs:
                logger.warning('Found devices that have no instance.  These will be removed from the table. '\
                               '{}', bad_devs)
                del_data = {
                    'instance': ''
                }
                self.dbwrapper.autoexec_delete('trs_status', del_data)
            sql = "SELECT `DATA_TYPE`\n"\
                  "FROM `INFORMATION_SCHEMA`.`COLUMNS`\n"\
                  "WHERE `TABLE_NAME` = 'trs_status' AND `COLUMN_NAME` = 'instance'"
            res = self.dbwrapper.autofetch_value(sql)
            if res:
                instances = {
                    self._application_args.status_name: self.instance_id
                }
                # We dont want to mess with collations so just pull in and compare
                sql = "SELECT `instance`, `origin` FROM `trs_status`"
                try:
                    devs = self.dbwrapper.autofetch_all(sql)
                    if devs is None:
                        devs = []
                except:
                    devs = []
                for dev in devs:
                    if dev['instance'] not in instances:
                        tmp_instance = self.dbwrapper.get_instance_id(instance_name=dev['instance'])
                        instances[dev['instance']] = tmp_instance
                    update_data = {
                        'instance_id': instances[dev['instance']]
                    }
                    self.dbwrapper.autoexec_update('trs_status', update_data, where_keyvals=dev)
                # Drop the old column
                alter_query = (
                    "ALTER TABLE trs_status "
                    "DROP instance"
                )
                try:
                    self.dbwrapper.execute(alter_query, commit=True)
                except Exception as e:
                    logger.exception("Unexpected error: {}", e)

        self.set_version(current_version)

    def set_version(self, version):
        output = {'version': version}
        with open('version.json', 'w') as outfile:
            json.dump(output, outfile)

    def __convert_geofence(self, path):
        stripped_data = []
        full_path = Path(path)
        with open(full_path) as f:
            for line in f:
                stripped = line.strip()
                if type(stripped) != str:
                    stripped = stripped.decode('utf-8')
                stripped_data.append(stripped)
        resource = self.data_manager.get_resource('geofence')
        name = path
        # Enforce 128 character limit
        if len(name) > 128:
            name = name[len(name)-128:]
        update_data = {
            'name': path,
            'fence_type': 'polygon',
            'fence_data': stripped_data
        }
        resource.update(update_data)
        resource.save(force_insert=True)
        return resource.identifier

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
