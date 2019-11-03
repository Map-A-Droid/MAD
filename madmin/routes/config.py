import ast
import os
import json
import glob
from flask import (render_template, request, redirect, url_for, Response)
from flask_caching import Cache
from functools import cmp_to_key
from madmin.functions import auth_required
from utils.language import i8ln, open_json_file
from utils.adb import ADBConnect
from utils.MappingManager import MappingManager
from utils.logging import logger
import re

cache = Cache(config={'CACHE_TYPE': 'simple'})


class config(object):
    def __init__(self, db, args, logger, app, mapping_manager: MappingManager, data_manager):
        self._db = db
        self._args = args
        if self._args.madmin_time == "12":
            self._datetimeformat = '%Y-%m-%d %I:%M:%S %p'
        else:
            self._datetimeformat = '%Y-%m-%d %H:%M:%S'
        self._adb_connect = ADBConnect(self._args)
        self._ws_connected_phones: list = []
        self._logger = logger
        self._data_manager = data_manager
        self._app = app
        self._app.config["TEMPLATES_AUTO_RELOAD"] = True
        cache.init_app(self._app)
        self._mapping_mananger = mapping_manager

        self.add_route()

    def add_route(self):
        routes = [
            ("/settings", self.settings),
            ("/settings/areas", self.settings_areas),
            ("/settings/auth", self.settings_auth),
            ("/settings/devices", self.settings_devices),
            ("/settings/ivlists", self.settings_ivlists),
            ("/settings/monsearch", self.monsearch),
            ("/settings/shared", self.settings_pools),
            ("/settings/walker", self.settings_walkers),
            ("/settings/walker/areaeditor", self.settings_walker_area),
            ("/reload", self.reload)
        ]
        for route, view_func in routes:
            self._app.route(route, methods=['GET', 'POST'])(view_func)

    def get_pokemon(self):
        mondata = open_json_file('pokemon')
        # Why o.O
        stripped_mondata = {}
        for mon_id in mondata:
            stripped_mondata[mondata[str(mon_id)]["name"]] = mon_id
            if os.environ['LANGUAGE'] != "en":
                try:
                    localized_name = i8ln(mondata[str(mon_id)]["name"])
                    stripped_mondata[localized_name] = mon_id
                except KeyError:
                    pass
        return {
            'mondata': mondata,
            'locale': stripped_mondata
        }

    @auth_required
    @logger.catch
    def monsearch(self):
        search = request.args.get('search')
        pokemon = []
        if search or (search and len(search) >= 3):
            all_pokemon = self.get_pokemon()
            r = re.compile('.*%s.*' % (re.escape(search)), re.IGNORECASE)
            mon_names = list(filter(r.search, all_pokemon['locale'].keys()))
            for name in sorted(mon_names):
                mon_id = all_pokemon['locale'][name]
                pokemon.append({"mon_name": name, "mon_id": str(mon_id)})
        return Response(json.dumps(pokemon), mimetype='application/json')

    def process_element(self, **kwargs):
        identifier = request.args.get(kwargs.get('identifier'))
        base_uri = kwargs.get('base_uri')
        data_source = kwargs.get('data_source')
        redirect_uri = url_for(kwargs.get('redirect'))
        html_single = kwargs.get('html_single')
        html_all = kwargs.get('html_all')
        subtab = kwargs.get('subtab')
        var_parser_section = kwargs.get('var_parser_section', subtab)
        required_data = kwargs.get('required_data', {})
        mode_required = kwargs.get('mode_required', False)
        passthrough = kwargs.get('passthrough', {})
        try:
            int(identifier)
        except ValueError:
            if identifier != 'new':
                return redirect(url_for(kwargs.get('redirect')), code=302)
        except TypeError:
            pass
        mode = request.args.get("mode", None)
        settings_vars = self.process_settings_vars(self._data_manager.get_api_attribute(subtab, 'configuration'), mode=mode)
        if request.method == 'GET':
            included_data = {
                'advcfg': self._args.advanced_config,
                'base_uri': url_for(base_uri),
                'identifier': identifier
            }
            for key, data_section in required_data.items():
                included_data[key] = self._data_manager.get_data(data_section)
            for key, val in passthrough.items():
                included_data[key] = val
            # Mode was required for this operation but was not present.  Return the base element
            if mode_required and mode is None:
                try:
                    req = self._data_manager.get_data(data_source, identifier=identifier)
                    element = req
                    included_data[subtab] = element
                    return render_template(html_all,
                                           subtab=subtab,
                                           **included_data
                                           )
                except:
                    return redirect(redirect_uri, code=302)
            if identifier and identifier == 'new':
                return render_template(html_single,
                                       uri=included_data['base_uri'],
                                       redirect=redirect_uri,
                                       element={'settings':{}},
                                       subtab=subtab,
                                       method='POST',
                                       settings_vars=settings_vars,
                                       **included_data)
            req = self._data_manager.get_data(data_source, identifier=identifier)
            element = req
            included_data[subtab] = element
            if identifier is not None:
                return render_template(html_single,
                                       uri='%s/%s' % (included_data['base_uri'], identifier),
                                       redirect=redirect_uri,
                                       element=element,
                                       subtab=subtab,
                                       method='PATCH',
                                       settings_vars=settings_vars,
                                       **included_data)
            else:
                return render_template(html_all,
                                       subtab=subtab,
                                       **included_data
                                       )

    def process_settings_vars(self, config, mode=None):
        try:
            return config[mode]
        except KeyError:
            return config

    @logger.catch
    @auth_required
    def settings_areas(self):
        fences = {}
        geofence_file_path = self._args.geofence_file_path
        existing_fences = sorted(glob.glob(os.path.join(geofence_file_path, '*.txt')))
        for geofence_temp in existing_fences:
            fences[geofence_temp] = os.path.basename(geofence_temp)
        required_data = {
            'identifier': 'id',
            'base_uri': 'api_area',
            'data_source': 'area',
            'redirect': 'settings_areas',
            'html_single': 'settings_singlearea.html',
            'html_all': 'settings_areas.html',
            'subtab': 'area',
            'required_data': {
                'monlist': 'monivlist'
            },
            'passthrough': {
                'fences': fences
            },
            'mode_required': True
        }
        return self.process_element(**required_data)

    @logger.catch
    @auth_required
    def settings_auth(self):
        required_data = {
            'identifier': 'id',
            'base_uri': 'api_auth',
            'data_source': 'auth',
            'redirect': 'settings_auth',
            'html_single': 'settings_singleauth.html',
            'html_all': 'settings_auth.html',
            'subtab': 'auth',
        }
        return self.process_element(**required_data)

    @logger.catch
    @auth_required
    def settings_devices(self):
        required_data = {
            'identifier': 'id',
            'base_uri': 'api_device',
            'data_source': 'device',
            'redirect': 'settings_devices',
            'html_single': 'settings_singledevice.html',
            'html_all': 'settings_devices.html',
            'subtab': 'device',
            'required_data': {
                'walkers': 'walker',
                'pools': 'devicesetting'
            },
        }
        return self.process_element(**required_data)

    @logger.catch
    @auth_required
    def settings_ivlists(self):
        try:
            identifier = request.args.get('id')
            current_mons = self._data_manager.get_data('monivlist', identifier)['mon_ids_iv']
        except Exception as err:
            current_mons = []
        all_pokemon = self.get_pokemon()
        mondata = all_pokemon['mondata']
        current_mons_list = []
        for mon_id in current_mons:
            try:
                mon_name = i8ln(mondata[str(mon_id)]["name"])
            except KeyError:
                mon_name = "No-name-in-file-please-fix"
            current_mons_list.append({"mon_name": mon_name, "mon_id": str(mon_id)})
        required_data = {
            'identifier': 'id',
            'base_uri': 'api_monivlist',
            'data_source': 'monivlist',
            'redirect': 'settings_ivlists',
            'html_single': 'settings_singleivlist.html',
            'html_all': 'settings_ivlists.html',
            'subtab': 'monivlist',
            'passthrough': {
                'current_mons_list': current_mons_list
            }
        }
        return self.process_element(**required_data)

    @logger.catch
    @auth_required
    def settings_pools(self):
        required_data = {
            'identifier': 'id',
            'base_uri': 'api_devicesetting',
            'data_source': 'devicesetting',
            'redirect': 'settings_pools',
            'html_single': 'settings_singlesharedsetting.html',
            'html_all': 'settings_sharedsettings.html',
            'subtab': 'devicesetting',
            'var_parser_section': 'devices',
            'required_data': {},
        }
        return self.process_element(**required_data)

    @logger.catch
    @auth_required
    def settings_walkers(self):
        required_data = {
            'identifier': 'id',
            'base_uri': 'api_walker',
            'data_source': 'walker',
            'redirect': 'settings_walkers',
            'html_single': 'settings_singlewalker.html',
            'html_all': 'settings_walkers.html',
            'subtab': 'walker',
            'required_data': {
                'areas': 'area',
                'walkerarea': 'walkerarea'
            },
        }
        return self.process_element(**required_data)

    @logger.catch
    @auth_required
    def settings_walker_area(self):
        walkerarea_id = request.args.get("walkerarea", None)
        walker_id = request.args.get("id", None)
        if walker_id is None:
            return redirect(url_for('settings_walkers'), code=302)
        # Only pull this if its set.  When creating a new walkerarea it will be empty
        if walkerarea_id is not None:
            walkerarea_uri = '%s/%s' % (url_for('api_walkerarea'), walkerarea_id)
            walkerareaconfig = self._data_manager.get_data('walkerarea', identifier=walkerarea_id)
        else:
            walkerarea_uri = url_for('api_walkerarea')
            walkerareaconfig = {}
        walkerconfig = self._data_manager.get_data('walker', identifier=walker_id)
        areaconfig = self._data_manager.get_data('area')
        walkertypes = ['coords','countdown', 'idle', 'period', 'round', 'timer']
        mappings = {
            'uri': walkerarea_uri,
            'element': walkerareaconfig,
            'walker': walkerconfig,
            'walkeruri': walker_id,
            'areas': areaconfig,
            'walkertypes': walkertypes,
            'redirect': url_for('settings_walkers')
        }
        return render_template('settings_walkerarea.html',
                               subtab="walker",
                               **mappings
                               )

    @logger.catch
    @auth_required
    def settings(self):
        return redirect(url_for('settings_devices'), code=302)

    @auth_required
    def reload(self):
        if not self._args.auto_reload_config:
            self._mapping_mananger.update()
        return redirect(url_for('settings_devices'), code=302)
