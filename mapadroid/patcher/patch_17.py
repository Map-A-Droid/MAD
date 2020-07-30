from ._patch_base import PatchBase
import copy
import json
import os
from pathlib import Path
import mapadroid.data_manager.modules
from mapadroid.data_manager.dm_exceptions import (
    UpdateIssue
)


class Patch(PatchBase):
    name = 'Database Migration'

    def _execute(self):
        try:
            # Goodbye mappings.json, it was nice knowing ya!
            update_order = ['monivlist', 'auth', 'devicesettings', 'areas', 'walkerarea', 'walker',
                            'devices']
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
                self._logger.info('Found a {} with an ID of 0.  Setting ID to {}', section, cache[section])
                # Update the trs_status table to reflect the latest
                if section == 'areas':
                    updated = {
                        'routemanager': cache[section]
                    }
                    where = {
                        'routemanager': 0
                    }
                    self._db.autoexec_update('trs_status', updated, where_keyvals=where)
            if cache:
                self._logger.info(
                    'One or more resources with ID 0 found.  Converting them off 0 and updating the '
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
                    except KeyError:
                        mode = None
                    resource_def = self._data_manager.get_resource_def(dm_section, mode=mode)
                    sql = "SELECT `%s` FROM `%s` WHERE `%s` = %%s AND `instance_id` != %%s"
                    sql_args = (resource_def.primary_key, resource_def.table, resource_def.primary_key)
                    sql_format_args = (elem_id, self._data_manager.instance_id)
                    exists = self._db.autofetch_value(sql % sql_args, args=sql_format_args)
                    if not exists:
                        continue
                    self._logger.info('{} {} already exists and a new ID will be generated', dm_section, elem_id)
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
                    self._logger.debug('Converting {} {}', section, key)
                    if section == 'areas':
                        mode = elem['mode']
                        del elem['mode']
                        resource = mapadroid.data_manager.modules.MAPPINGS['area'](
                            self._data_manager, mode=mode)
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
                                    except UpdateIssue as err:
                                        conversion_issues.append((section, elem_id, err.issues))
                                else:
                                    elem[geofence_section] = geofences[geofence]
                            except KeyError:
                                pass
                        route = '%s.calc' % (elem['routecalc'],)
                        if type(elem['routecalc']) is str:
                            if route not in routecalcs:
                                route_path = os.path.join(self._application_args.file_path, route)
                                route_resource = self._data_manager.get_resource('routecalc')
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
                                    self._logger.warning('Unable to open %s.  Using empty route' % (route))
                                route_resource['routefile'] = stripped_data
                                route_resource.save(force_insert=True)
                                routecalcs[route] = route_resource.identifier
                            if route in routecalcs:
                                elem['routecalc'] = routecalcs[route]
                    else:
                        resource = mapadroid.data_manager.modules.MAPPINGS[dm_section](
                            self._data_manager)
                    # Settings made it into some configs where it should not be.  lets clear those out now
                    if 'settings' in elem and 'settings' not in resource.configuration:
                        del elem['settings']
                    # Update any IDs that have been converted.  There are no required updates for monivlist, auth,
                    # or devicesettings as they are not dependent on other resources
                    if dm_section == 'area':
                        try:
                            monlist = elem['settings']['mon_ids_iv']
                            elem['settings']['mon_ids_iv'] = generate_new_ids['monivlist'][monlist]
                            save_elem['settings']['mon_ids_iv'] = str(
                                generate_new_ids['monivlist'][monlist])
                            self._logger.info('Updating monivlist from {} to {}', key,
                                              elem['settings']['mon_ids_iv'])
                        except KeyError:
                            pass
                    elif dm_section == 'device':
                        try:
                            pool_id = elem['pool']
                            elem['pool'] = generate_new_ids['devicepool'][pool_id]
                            save_elem['pool'] = str(generate_new_ids['devicepool'][pool_id])
                            self._logger.info('Updating device pool from {} to {}', pool_id, elem['pool'])
                        except KeyError:
                            pass
                        try:
                            walker_id = elem['walker']
                            elem['walker'] = generate_new_ids['walker'][walker_id]
                            save_elem['walker'] = str(generate_new_ids['walker'][walker_id])
                            self._logger.info('Updating device walker from {} to {}', walker_id, elem['walker'])
                        except KeyError:
                            pass
                    elif dm_section == 'walker':
                        new_list = []
                        for walkerarea_id in elem['setup']:
                            try:
                                new_list.append(str(generate_new_ids['walkerarea'][walkerarea_id]))
                                self._logger.info('Updating walker-walkerarea from {} to {}', walkerarea_id,
                                                  new_list[-1])
                            except KeyError:
                                new_list.append(walkerarea_id)
                        elem['setup'] = new_list
                        save_elem['setup'] = new_list
                    elif dm_section == 'walkerarea':
                        try:
                            area_id = elem['walkerarea']
                            elem['walkerarea'] = generate_new_ids['area'][area_id]
                            save_elem['walkerarea'] = str(generate_new_ids['area'][area_id])
                            self._logger.info('Updating walkerarea from {} to {}', area_id, elem['walkerarea'])
                        except KeyError:
                            pass
                    save_new_id = False
                    try:
                        generate_new_ids[dm_section][key]
                        save_new_id = True
                    except KeyError:
                        resource.identifier = key
                    resource.update(elem)
                    try:
                        resource.save(force_insert=True, ignore_issues=['unknown'])
                    except UpdateIssue as err:
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
                self._logger.error(
                    'The configuration was not partially moved to the database.  The following resources '
                    'were not converted.')
                for (section, identifier, issue) in conversion_issues:
                    self._logger.error('{} {}: {}', section, identifier, issue)
            if generate_new_ids:
                with open(self._application_args.mappings, 'w') as outfile:
                    json.dump(config_file, outfile, indent=4, sort_keys=True)
        except IOError:
            pass

    def __convert_geofence(self, path):
        stripped_data = []
        full_path = Path(path)
        with open(full_path) as f:
            for line in f:
                stripped = line.strip()
                if type(stripped) != str:
                    stripped = stripped.decode('utf-8')
                stripped_data.append(stripped)
        resource = self._data_manager.get_resource('geofence')
        name = path
        # Enforce 128 character limit
        if len(name) > 128:
            name = name[len(name) - 128:]
        update_data = {
            'name': path,
            'fence_type': 'polygon',
            'fence_data': stripped_data
        }
        resource.update(update_data)
        resource.save(force_insert=True)
        return resource.identifier
