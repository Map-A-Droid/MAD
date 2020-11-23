import json
import os
import re
from flask import (render_template, request, redirect, url_for, Response)
from flask_caching import Cache
from typing import List, Tuple
from mapadroid.data_manager import DataManagerException
from mapadroid.madmin.functions import auth_required
from mapadroid.utils.MappingManager import MappingManager
from mapadroid.utils.adb import ADBConnect
from mapadroid.utils.language import i8ln, open_json_file
from mapadroid.data_manager.dm_exceptions import (
    ModeNotSpecified,
    ModeUnknown
)
from mapadroid.data_manager.modules.pogoauth import PogoAuth
from mapadroid.utils.logging import get_logger, LoggerEnums


logger = get_logger(LoggerEnums.madmin)
cache = Cache(config={'CACHE_TYPE': 'simple'})


class MADminConfig(object):
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

    def add_route(self):
        routes = [
            ("/settings", self.settings),
            ("/settings/areas", self.settings_areas),
            ("/settings/auth", self.settings_auth),
            ("/settings/devices", self.settings_devices),
            ("/settings/geofence", self.settings_geofence),
            ("/settings/ivlists", self.settings_ivlists),
            ("/settings/pogoauth", self.settings_pogoauth),
            ("/settings/monsearch", self.monsearch),
            ("/settings/shared", self.settings_pools),
            ("/settings/routecalc", self.settings_routecalc),
            ("/settings/walker", self.settings_walkers),
            ("/settings/walker/areaeditor", self.settings_walker_area),
            ("/recalc_status", self.recalc_status),
            ("/reload", self.reload)
        ]
        for route, view_func in routes:
            self._app.route(route, methods=['GET', 'POST'])(view_func)

    def start_modul(self):
        self.add_route()

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
            mon_search_compiled = re.compile('.*%s.*' % (re.escape(search)), re.IGNORECASE)
            mon_names = list(filter(mon_search_compiled.search, all_pokemon['locale'].keys()))
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
        section = kwargs.get('section', subtab)
        var_parser_section = kwargs.get('var_parser_section', section)  # noqa:F841
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
        if mode_required and mode is None:
            try:
                req = self._data_manager.get_resource(data_source, identifier=identifier)
                mode = req.area_type
            except DataManagerException:
                if identifier:
                    return redirect(redirect_uri, code=302)
                else:
                    pass
        try:
            settings_vars = self._data_manager.get_settings(section, mode=mode)
        except (ModeNotSpecified, ModeUnknown):
            if identifier:
                raise
            else:
                settings_vars = {}
        if request.method == 'GET':
            included_data = {
                'base_uri': url_for(base_uri),
                'identifier': identifier
            }
            for key, data_section in required_data.items():
                included_data[key] = self._data_manager.get_root_resource(data_section)
            for key, value in passthrough.items():
                included_data[key] = value
            if identifier and identifier == 'new':
                return render_template(html_single,
                                       uri=included_data['base_uri'],
                                       redirect=redirect_uri,
                                       element={'settings': {}},
                                       subtab=subtab,
                                       method='POST',
                                       settings_vars=settings_vars,
                                       **included_data)
            if identifier is not None:
                req = self._data_manager.get_resource(data_source, identifier=identifier)
                element = req
                included_data[section] = element
                return render_template(html_single,
                                       uri='%s/%s' % (included_data['base_uri'], identifier),
                                       redirect=redirect_uri,
                                       element=element,
                                       subtab=subtab,
                                       method='PATCH',
                                       settings_vars=settings_vars,
                                       **included_data)
            else:
                included_data[section] = self._data_manager.get_root_resource(data_source)
                return render_template(html_all,
                                       subtab=subtab,
                                       **included_data
                                       )

    @logger.catch
    @auth_required
    def recalc_status(self):
        recalc = []
        areas = self._data_manager.get_root_resource('area')
        for area_id, area in areas.items():
            if area.recalc_status:
                recalc.append(area_id)
        return Response(json.dumps(recalc), mimetype='application/json')

    @logger.catch
    @auth_required
    def settings_areas(self):
        fences = {}
        raw_fences = self._data_manager.get_root_resource('geofence')
        for fence_id, fence_data in raw_fences.items():
            fences[fence_id] = fence_data['name']

        # check if we can use ortools and if it's installed
        ortools_info = False

        try:
            from ortools.constraint_solver import routing_enums_pb2
            from ortools.constraint_solver import pywrapcp
        except Exception:
            pass
        import platform

        if platform.architecture()[0] == "64bit":
            try:
                pywrapcp
                routing_enums_pb2
            except Exception:
                ortools_info = True

        required_data = {
            'identifier': 'id',
            'base_uri': 'api_area',
            'data_source': 'area',
            'redirect': 'settings_areas',
            'html_single': 'settings_singlearea.html',
            'html_all': 'settings_areas.html',
            'subtab': 'area',
            'required_data': {
                'monlist': 'monivlist',
                'fences': 'geofence'
            },
            'passthrough': {
                'config_mode': self._args.config_mode,
                'ortools_info': ortools_info,
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
        try:
            identifier = request.args.get('id')
            int(identifier)
        except (TypeError, ValueError):
            pass
        ggl_accounts = PogoAuth.get_avail_accounts(self._data_manager,
                                                   'google',
                                                   device_id=identifier)
        ptc_accounts = []
        for account_id, account in PogoAuth.get_avail_accounts(self._data_manager,
                                                               'ptc',
                                                               device_id=identifier).items():
            ptc_accounts.append({
                'text': account['username'],
                'id': account_id
            })
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
                'pools': 'devicepool'
            },
            'passthrough': {
                'ggl_accounts': ggl_accounts,
                'ptc_accounts': ptc_accounts,
                'requires_auth': not self._args.autoconfig_no_auth,
                'responsive': str(self._args.madmin_noresponsive).lower()
            }
        }
        return self.process_element(**required_data)

    @logger.catch
    @auth_required
    def settings_geofence(self):
        required_data = {
            'identifier': 'id',
            'base_uri': 'api_geofence',
            'data_source': 'geofence',
            'redirect': 'settings_geofence',
            'html_single': 'settings_singlegeofence.html',
            'html_all': 'settings_geofences.html',
            'subtab': 'geofence',
        }
        return self.process_element(**required_data)

    @logger.catch
    @auth_required
    def settings_ivlists(self):
        try:
            identifier = request.args.get('id')
            current_mons = self._data_manager.get_resource('monivlist', identifier)['mon_ids_iv']
        except Exception:
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
    def settings_pogoauth(self):
        devices = self._data_manager.get_root_resource('device')
        devs_google: List[Tuple[int, str]] = []
        devs_ptc: List[Tuple[int, str]] = []
        current_id = request.args.get('id', None)
        try:
            identifier = int(current_id)
        except (TypeError, ValueError):
            identifier = None
        for dev_id, dev in PogoAuth.get_avail_devices(self._data_manager,
                                                      auth_id=identifier).items():
            devs_google.append((dev_id, dev['origin']))
        for dev_id, dev in PogoAuth.get_avail_devices(self._data_manager,
                                                      auth_id=identifier).items():
            devs_ptc.append((dev_id, dev['origin']))
        required_data = {
            'identifier': 'id',
            'base_uri': 'api_pogoauth',
            'data_source': 'pogoauth',
            'redirect': 'settings_pogoauth',
            'html_single': 'settings_singlepogoauth.html',
            'html_all': 'settings_pogoauth.html',
            'subtab': 'pogoauth',
            'passthrough': {
                'devices': devices,
                'devs_google': devs_google,
                'devs_ptc': devs_ptc
            },
        }
        return self.process_element(**required_data)

    @logger.catch
    @auth_required
    def settings_pools(self):
        required_data = {
            'identifier': 'id',
            'base_uri': 'api_devicepool',
            'data_source': 'devicepool',
            'redirect': 'settings_pools',
            'html_single': 'settings_singlesharedsetting.html',
            'html_all': 'settings_sharedsettings.html',
            'subtab': 'devicepool',
            'var_parser_section': 'devices',
            'required_data': {},
        }
        return self.process_element(**required_data)

    @logger.catch
    @auth_required
    def settings_routecalc(self):
        try:
            area_id = request.args.get('area_id')
            area = self._data_manager.get_resource('area', identifier=area_id)
            if area['routecalc'] != int(request.args.get('id')):
                return redirect(url_for('settings_areas'), code=302)
        except DataManagerException:
            return redirect(url_for('settings_areas'), code=302)
        required_data = {
            'identifier': 'id',
            'base_uri': 'api_routecalc',
            'data_source': 'routecalc',
            'redirect': 'settings_areas',
            'html_single': 'settings_singleroutecalc.html',
            'html_all': 'settings_singleroutecalc.html',
            'subtab': 'area',
            'section': 'routecalc',
            'passthrough': {
                'areaname': area['name']
            }
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
            walkerareaconfig = self._data_manager.get_resource('walkerarea', identifier=walkerarea_id)
        else:
            walkerarea_uri = url_for('api_walkerarea')
            walkerareaconfig = {}
        walkerconfig = self._data_manager.get_resource('walker', identifier=walker_id)
        areaconfig = self._data_manager.get_root_resource('area')
        walkertypes = ['coords', 'countdown', 'idle', 'period', 'round', 'timer']
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
        self._mapping_mananger.update()
        return redirect(url_for('settings_devices'), code=302)
