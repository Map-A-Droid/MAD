import ast
import os
import json
from flask import (render_template, request, redirect, url_for)
from flask_caching import Cache
from functools import cmp_to_key
from madmin.functions import auth_required, getBasePath
from utils.language import i8ln, open_json_file
from utils.adb import ADBConnect
from utils.MappingManager import MappingManager
from utils.logging import logger

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
            ("/showmonsidpicker", self.showmonsidpicker),
            ("/settings", self.settings),
            ("/settings/auth", self.settings_auth),
            ("/settings/devices", self.settings_devices),
            ("/settings/shared", self.settings_shared),
            ("/settings/areas", self.settings_areas),
            ("/settings/walker", self.settings_walkers),
            ("/settings/walker/areaeditor", self.setting_walkers_area),
            ("/reload", self.reload)
        ]
        for route, view_func in routes:
            self._app.route(route, methods=['GET', 'POST'])(view_func)

    def process_element(self, **kwargs):
        key = kwargs.get('identifier')
        base_uri = kwargs.get('base_uri')
        redirect = kwargs.get('redirect')
        html_single = kwargs.get('html_single')
        html_all = kwargs.get('html_all')
        subtab = kwargs.get('subtab')
        var_parser_section = kwargs.get('var_parser_section', subtab)
        required_uris = kwargs.get('required_uris')
        mode_required = kwargs.get('mode_required', False)
        identifier = request.args.get(key)
        uri = identifier
        if uri:
            if base_uri not in uri:
                uri = '%s/%s' % (base_uri, identifier)
        else:
            uri = base_uri
        mode = request.args.get("mode", None)
        settings_vars = self.process_settings_vars(self._data_manager.get_api_attribute(subtab, 'configuration'), mode=mode)
        if request.method == 'GET':
            included_data = {}
            if required_uris:
                for key, tmp_uri in required_uris.items():
                    included_data[key] = self._data_manager.get_data(tmp_uri)
            # Mode was required for this operation but was not present.  Return the base element
            if mode_required and mode is None:
                req = self._data_manager.get_data(base_uri)
                element = req
                included_data[subtab] = element
                return render_template(html_all,
                                       subtab=subtab,
                                       **included_data
                                       )
            if identifier and identifier == 'new':
                return render_template(html_single,
                                       uri=base_uri,
                                       redirect=redirect,
                                       element={'settings':{}},
                                       subtab=subtab,
                                       method='POST',
                                       settings_vars=settings_vars,
                                       **included_data)
            req = self._data_manager.get_data(uri)
            element = req
            included_data[subtab] = element
            if identifier:
                return render_template(html_single,
                                       uri=uri,
                                       redirect=redirect,
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
        required_data = {
            'identifier': 'id',
            'base_uri': '/api/area',
            'redirect': '/settings/areas',
            'html_single': 'settings_singlearea.html',
            'html_all': 'settings_areas.html',
            'subtab': 'area',
            'mode_required': True
        }
        return self.process_element(**required_data)

    @logger.catch
    @auth_required
    def settings_auth(self):
        required_data = {
            'identifier': 'id',
            'base_uri': '/api/auth',
            'redirect': '/settings/auth',
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
            'base_uri': '/api/device',
            'redirect': '/settings/devices',
            'html_single': 'settings_singledevice.html',
            'html_all': 'settings_devices.html',
            'subtab': 'device',
            'required_uris': {
                'walkers': '/api/walker',
                'pools': '/api/devicesetting'
            },
        }
        return self.process_element(**required_data)

    @logger.catch
    @auth_required
    def settings_shared(self):
        required_data = {
            'identifier': 'id',
            'base_uri': '/api/devicesetting',
            'redirect': '/settings/shared',
            'html_single': 'settings_singlesharedsetting.html',
            'html_all': 'settings_sharedsettings.html',
            'subtab': 'devicesetting',
            'var_parser_section': 'devices',
            'required_uris': {},
        }
        return self.process_element(**required_data)

    @logger.catch
    @auth_required
    def settings_walkers(self):
        required_data = {
            'identifier': 'id',
            'base_uri': '/api/walker',
            'redirect': '/settings/walker',
            'html_single': 'settings_singlewalker.html',
            'html_all': 'settings_walkers.html',
            'subtab': 'walker',
            'required_uris': {
                'areas': '/api/area',
                'walkerarea': '/api/walkerarea'
            },
        }
        return self.process_element(**required_data)

    @logger.catch
    @auth_required
    def setting_walkers_area(self):
        walkerarea_uri = request.args.get("walkerarea", None)
        walkeruri = request.args.get("id", None)
        if walkeruri is None:
            return self.settings_walkers()
        # Only pull this if its set.  When creating a new walkerarea it will be empty
        if walkerarea_uri is not None:
            if '/api/walkerarea/' not in walkerarea_uri:
                walkerarea_uri = '/api/walkerarea/%s' % (walkerarea_uri,)
            walkerareaconfig = self._data_manager.get_data(walkerarea_uri)
        else:
            walkerarea_uri = '/api/walkerarea'
            walkerareaconfig = {}
        if '/api/walker/' not in walkeruri:
            walkeruri = '/api/walker/%s' % (walkeruri,)
        walkerconfig = self._data_manager.get_data(walkeruri)
        areaconfig = self._data_manager.get_data('/api/area')
        walkertypes = ['coords','countdown', 'idle', 'period', 'round', 'timer']
        mappings = {
            'uri': walkerarea_uri,
            'element': walkerareaconfig,
            'walker': walkerconfig,
            'walkeruri': walkeruri,
            'areas': areaconfig,
            'walkertypes': walkertypes
        }
        return render_template('settings_walkerarea.html',
                               subtab="walker",
                               **mappings
                               )

    @logger.catch
    @auth_required
    def settings(self):
        return redirect("/{}/settings/devices".format(self._args.madmin_base_path), code=302)

    @auth_required
    @logger.catch
    def showmonsidpicker(self):
        edit = request.args.get('edit')
        type = request.args.get('type')
        header = ""
        title = ""

        if request.method == 'GET' and (not edit or not type):
            return render_template('showmonsidpicker.html', error_msg="How did you end up here? Missing params.",
                                   header=header, title=title)

        with open(self._args.mappings) as f:
            mapping = json.load(f)

        if "areas" not in mapping:
            return render_template('showmonsidpicker.html',
                                   error_msg="No areas defined at all, please configure first.", header=header,
                                   title=title)

        this_area = None
        this_area_index = -1
        for t_area in mapping["monivlist"]:
            this_area_index += 1
            if t_area['monlist'] == edit:
                this_area = t_area
                break

        if this_area == None:
            return render_template('showmonsidpicker.html',
                                   error_msg="No area (" + edit + " with mode: " + type + ") found in mappings, add it first.",
                                   header=header, title=title)

        title = "Mons ID Picker for " + edit
        header = "Editing area " + edit + " (" + type + ")"
        backurl = "config?type=" + type + "&area=monivlist&block=fields&edit=" + edit


        if request.method == 'POST':
            new_mons_list = request.form.get('current_mons_list')
            if not new_mons_list:
                return redirect("/showsettings", code=302)

            mapping["monivlist"][this_area_index]["mon_ids_iv"] = ast.literal_eval(new_mons_list)

            with open(self._args.mappings, 'w') as outfile:
                json.dump(mapping, outfile, indent=4, sort_keys=True)
            return redirect(backurl, code=302)

        if "mon_ids_iv" not in this_area:
            current_mons = []
        else:
            current_mons = this_area["mon_ids_iv"]

        mondata = open_json_file('pokemon')

        current_mons_list = []

        for mon_id in current_mons:
            try:
                mon_name = i8ln(mondata[str(mon_id)]["name"])
            except KeyError:
                mon_name = "No-name-in-file-please-fix"
            current_mons_list.append({"mon_name": mon_name, "mon_id": str(mon_id)})

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

        formhiddeninput = '<form action="showmonsidpicker?edit=' + edit + '&type=' + type + '" id="showmonsidpicker" method="post">'
        formhiddeninput += '<input type="hidden" id="current_mons_list" name="current_mons_list" value="' + str(
            current_mons) + '">'
        formhiddeninput += '<button type="submit" class="btn btn-success">Save</button></form>'
        return render_template('showmonsidpicker.html', backurl=backurl, formhiddeninput=formhiddeninput,
                               current_mons_list=current_mons_list, stripped_mondata=stripped_mondata, header=header,
                               title=title)

    @auth_required
    def reload(self):
        if not self._args.auto_reload_config:
            self._mapping_mananger.update()
        return redirect("/{}/settings".format(self._args.madmin_base_path), code=302)
