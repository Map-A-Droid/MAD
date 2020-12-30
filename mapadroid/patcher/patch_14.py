import json
import shutil

from ._patch_base import PatchBase


class Patch(PatchBase):
    name = 'Patch 14'

    def _execute(self):
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
                                for _, area in enumerate(entry['setup']):
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
                                        self._logger.error('DeviceSettings {} is not valid', entry['pool'])
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
