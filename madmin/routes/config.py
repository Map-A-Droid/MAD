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
    def __init__(self, db, args, logger, app, mapping_manager: MappingManager):
        self._db = db
        self._args = args
        if self._args.madmin_time == "12":
            self._datetimeformat = '%Y-%m-%d %I:%M:%S %p'
        else:
            self._datetimeformat = '%Y-%m-%d %H:%M:%S'
        self._adb_connect = ADBConnect(self._args)
        self._ws_connected_phones: list = []
        self._logger = logger

        self._app = app
        self._app.config["TEMPLATES_AUTO_RELOAD"] = True
        cache.init_app(self._app)
        self._mapping_mananger = mapping_manager
        self.add_route()

    def add_route(self):
        routes = [
            ("/addwalker", self.addwalker),
            ("/savesortwalker", self.savesortwalker),
            ("/delwalker", self.delwalker),
            ("/delsetting", self.delsetting),
            ("/addnew", self.addnew),
            ("/showmonsidpicker", self.showmonsidpicker),
            ("/addedit", self.addedit),
            ("/settings", self.settings),
            ("/settings/devices", self.settings_devices),
            ("/settings/shared", self.settings_shared),
            ("/settings/areas", self.settings_areas),
            ("/settings/set_device_walker", self.set_device_walker),
            ("/reload", self.reload)
        ]
        for route, view_func in routes:
            self._app.route(route, methods=['GET', 'POST'])(view_func)

    @auth_required
    def addwalker(self):
        fieldwebsite = []
        walkervalue = ""
        walkerposition = ""
        walkermax = ""
        walkertext = ""
        edit = request.args.get('edit')
        walker = request.args.get('walker')
        add = request.args.get('add')

        walkernr = request.args.get('walkernr')

        with open(self._args.mappings) as f:
            mapping = json.load(f)
            if 'walker' not in mapping:
                mapping['walker'] = []

        if add:
            walkerarea = request.args.get('walkerarea')
            walkertype = request.args.get('walkertype')
            walkervalue = request.args.get('walkervalue')
            walkernr = request.args.get('walkernr')
            walkermax = request.args.get('walkermax')
            walkertext = request.args.get('walkertext').replace(' ', '_')
            walkerposition = request.args.get('walkerposition', False)
            if not walkerposition:
                walkerposition = False
            oldwalkerposition = request.args.get('oldwalkerposition')
            edit = request.args.get('edit')

            walkerlist = {'walkerarea': walkerarea, 'walkertype': walkertype, 'walkervalue': walkervalue,
                          'walkermax': walkermax, 'walkertext': walkertext}

            if 'setup' not in mapping['walker'][int(walkernr)]:
                mapping['walker'][int(walkernr)]['setup'] = []

            if edit:
                if int(walkerposition) == int(oldwalkerposition):
                    mapping['walker'][int(walkernr)]['setup'][int(
                        walkerposition)] = walkerlist
                else:
                    del mapping['walker'][int(
                        walkernr)]['setup'][int(oldwalkerposition)]
                    if walkerposition:
                        mapping['walker'][int(walkernr)]['setup'].insert(
                            int(walkerposition), walkerlist)
                    else:
                        mapping['walker'][int(walkernr)]['setup'].insert(
                            999, walkerlist)
            else:
                if walkerposition:
                    mapping['walker'][int(walkernr)]['setup'].insert(
                        int(walkerposition), walkerlist)
                else:
                    mapping['walker'][int(walkernr)]['setup'].insert(
                        999, walkerlist)

            with open(self._args.mappings, 'w') as outfile:
                json.dump(mapping, outfile, indent=4, sort_keys=True)

                return redirect(getBasePath(request) + "/config?type=walker&area=walker&block=fields&edit="
                                + str(walker), code=302)

        if walker and edit:
            walkerposition = request.args.get('walkerposition')
            _walkerval = mapping['walker'][int(
                walkernr)]['setup'][int(walkerposition)]
            walkerarea = _walkerval['walkerarea']
            walkertype = _walkerval['walkertype']
            walkervalue = _walkerval['walkervalue']
            walkermax = _walkerval.get('walkermax', '')
            walkertext = _walkerval.get('walkertext', '').replace(' ', '_')
            if walkermax is None:
                walkermax = ''
            edit = True

        fieldwebsite.append('<form action="addwalker" id="settings">')
        fieldwebsite.append(
            '<input type="hidden" name="walker" value="' + walker + '">')
        fieldwebsite.append('<input type="hidden" name="add" value=True>')
        if walker and edit:
            fieldwebsite.append(
                '<input type="hidden" name="oldwalkerposition" value=' + str(walkerposition) + '>')
            fieldwebsite.append('<input type="hidden" name="edit" value=True>')
        fieldwebsite.append(
            '<input type="hidden" name="walkernr" value=' + str(walkernr) + '>')

        req = "required"

        # lockvalue = 'readonly'
        lockvalue = ''

        _temp = '<div class="form-group"><label>Area</label><br /><small class="form-text text-muted">Select the Area' \
                '</small><select class="form-control" name="walkerarea" ' + \
                lockvalue + ' ' + req + '>'
        with open(self._args.mappings) as f:
            mapping = json.load(f)
            if 'walker' not in mapping:
                mapping['walker'] = []
        mapping['areas'].append({'name': None})

        for option in mapping['areas']:
            sel = ''
            if edit:
                if str(walkerarea).lower() == str(option['name']).lower():
                    sel = 'selected'
            _temp = _temp + '<option value="' + str(option['name']) + '" ' + sel + '>' + str(
                option['name']) + '</option>'
            sel = ''
        _temp = _temp + '</select></div>'
        fieldwebsite.append(str(_temp))

        req = "required"
        _temp = '<div class="form-group"><label>Walkermode</label><br /><small class="form-text text-muted">' \
                'Choose the way to end the route:<br>' \
                '<b>countdown</b>: Kill worker after X seconds<br>' \
                '<b>timer</b>: Kill worker after X:XX o´clock (Format: 24h f.e. 21:30 -> 9:30 pm)<br>' \
                '<b>round</b>: Kill worker after X rounds<br>' \
                '<b>period</b>: Kill worker if outside the period (Format: 24h f.e. 7:00-21:00)<br>' \
                '<b>coords*</b>: Kill worker if no more coords are present<br>' \
                '<b>idle*</b>: Idle worker and close Pogo till time or in period (check sleepmode of phone - ' \
                'display must be on in this time!)<br>' \
                '<b>*Additionally for coords/idle (walkervalue):</b><br>' \
                '- Kill worker after X:XX o´clock (Format: 24h)<br>' \
                '- Kill worker if outside of a period (Format: 24h f.e. 7:00-21:00)<br>' \
                '</small>' \
                '<select class="form-control" name="walkertype" ' + lockvalue + ' ' + req + '>'
        _options = ('countdown#timer#round#period#coords#idle').split('#')
        for option in _options:
            if edit:
                if str(walkertype).lower() in str(option).lower():
                    sel = 'selected'
            _temp = _temp + '<option value="' + \
                    str(option) + '" ' + sel + '>' + str(option) + '</option>'
            sel = ''
        _temp = _temp + '</select></div>'
        fieldwebsite.append(str(_temp))

        fieldwebsite.append('<div class="form-group"><label>Value for Walkermode</label><br />'
                            '<small class="form-text text-muted"></small>'
                            '<input type="text" name="walkervalue" value="' + str(
            walkervalue) + '" data-rule-validatewalkervalue="true"></div>')

        fieldwebsite.append('<div class="form-group"><label>Max. Walker in Area</label><br />'
                            '<small class="form-text text-muted">Empty = infinitely</small>'
                            '<input type="text" name="walkermax" value="' + str(walkermax) + '"></div>')

        fieldwebsite.append('<div class="form-group"><label>Description</label><br />'
                            '<small class="form-text text-muted"></small>'
                            '<input type="text" name="walkertext" value="' + str(walkertext).replace('_',
                                                                                                     ' ') + '"></div>')

        fieldwebsite.append('<div class="form-group"><label>Position in Walker</label><br />'
                            '<small class="form-text text-muted">Set position in walker (0=first / empty=append on list)'
                            '</small>'
                            '<input type="text" name="walkerposition" value="' + str(walkerposition) + '"></div>')

        fieldwebsite.append(
            '<button type="submit" class="btn btn-primary">Save</button></form>')

        if edit:
            header = "Edit " + walkerarea + " (" + walker + ")"
        else:
            header = "Add new " + walker

        return render_template('parser.html', editform=fieldwebsite, header=header, title="edit settings",
                               running_ocr=(self._args.only_ocr))

    @auth_required
    def savesortwalker(self):
        walkernr = request.args.get('walkernr')
        data = request.args.getlist('position[]')
        edit = request.args.get('edit')
        datavalue = []

        with open(self._args.mappings) as f:
            mapping = json.load(f)
            if 'walker' not in mapping:
                mapping['walker'] = []

        for ase in data:
            _temp = ase.split("|")
            walkerlist = {'walkerarea': _temp[0], 'walkertype': _temp[1], 'walkervalue': _temp[2],
                          'walkermax': _temp[3],
                          'walkertext': _temp[4]}
            datavalue.append(walkerlist)

        mapping['walker'][int(walkernr)]['setup'] = datavalue

        with open(self._args.mappings, 'w') as outfile:
            json.dump(mapping, outfile, indent=4, sort_keys=True)

        return redirect(getBasePath(request) + "/config?type=walker&area=walker&block=fields&edit=" + str(edit),
                        code=302)

    @auth_required
    def delwalker(self):
        walker = request.args.get('walker')
        walkernr = request.args.get('walkernr')
        walkerposition = request.args.get('walkerposition')

        with open(self._args.mappings) as f:
            mapping = json.load(f)
            if 'walker' not in mapping:
                mapping['walker'] = []

        del mapping['walker'][int(walkernr)]['setup'][int(walkerposition)]

        with open(self._args.mappings, 'w') as outfile:
            json.dump(mapping, outfile, indent=4, sort_keys=True)

        return redirect(getBasePath(request) + "/config?type=walker&area=walker&block=fields&edit=" + str(walker),
                        code=302)

    @auth_required
    def delsetting(self):
        global device_mappings, areas
        edit = request.args.get('edit')
        area = request.args.get('area')

        with open(self._args.mappings) as f:
            mapping = json.load(f)
            if 'walker' not in mapping:
                mapping['walker'] = []

        for key, entry in enumerate(mapping[area]):
            if 'name' in entry:
                _checkfield = 'name'
            if 'origin' in entry:
                _checkfield = 'origin'
            if 'username' in entry:
                _checkfield = 'username'
            if 'walkername' in entry:
                _checkfield = 'walkername'
            if 'devicepool' in entry:
                _checkfield = 'devicepool'
            if 'monlist' in entry:
                _checkfield = 'monlist'

            if str(edit) == str(entry[_checkfield]):
                del mapping[area][key]

        with open(self._args.mappings, 'w') as outfile:
            json.dump(mapping, outfile, indent=4, sort_keys=True)

        return redirect(getBasePath(request) + "/showsettings", code=302)

    def check_float(self, number):
        try:
            float(number)
            return True
        except ValueError:
            return False

    @auth_required
    def addedit(self):
        data = request.form.to_dict(flat=False)
        datavalue = {}

        for ase in data:
            key = ','.join(data[ase])
            datavalue[ase] = key

        edit = datavalue.get("edit", False)
        block = datavalue.get("block", False)
        area = datavalue.get("area", False)
        mode = datavalue.get("mode", False)

        with open(self._args.mappings) as f:
            mapping = json.load(f)
            if 'walker' not in mapping:
                mapping['walker'] = []
            if 'devicesettings' not in mapping:
                mapping['devicesettings'] = []
            if 'monivlist' not in mapping:
                mapping['monivlist'] = []

        with open('madmin/static/vars/settings.json') as f:
            settings = json.load(f)

        if edit:
            for entry in mapping[area]:
                if 'name' in entry:
                    _checkfield = 'name'
                if 'origin' in entry:
                    _checkfield = 'origin'
                if 'username' in entry:
                    _checkfield = 'username'
                if 'walkername' in entry:
                    _checkfield = 'walkername'
                if 'devicepool' in entry:
                    _checkfield = 'devicepool'
                if 'monlist' in entry:
                    _checkfield = 'monlist'

                if str(edit) == str(entry[_checkfield]):
                    if str(block) == str("settings"):
                        for key, value in datavalue.items():
                            if value == '' or value == 'None':
                                if key in entry['settings']:
                                    del entry['settings'][key]
                            elif value in area:
                                continue
                            else:
                                if str(key) not in ('block', 'area', 'type', 'edit', 'mode'):
                                    entry['settings'][key] = self.match_type(value)

                    else:
                        for key, value in datavalue.items():
                            if value == '':
                                if key in entry:
                                    del entry[key]
                            elif value in area:
                                continue
                            else:
                                if str(key) in ('geofence'):
                                    entry[key] = value
                                elif str(key) not in ('block', 'area', 'type', 'edit'):
                                    entry[key] = self.match_type(value)

        else:
            new = {}
            for key, value in datavalue.items():
                if value != '' and value not in area:
                    if str(key) in ('geofence'):
                        new[key] = value
                    elif str(key) not in ('block', 'area', 'type', 'edit'):
                        new[key] = self.match_type(value)

            if str(block) == str("settings"):
                mapping[area]['settings'].append(new)
            else:
                if settings[area]['has_settings'] == 'true':
                    new['settings'] = {}
                mapping[area].append(new)

        with open(self._args.mappings, 'w') as outfile:
            json.dump(mapping, outfile, indent=4, sort_keys=True)

        return redirect(getBasePath(request) + "/showsettings?area=" + str(area), code=302)

    def match_type(self, value):
        if '[' in value and ']' in value:
            if ':' in value:
                tempvalue = []
                valuearray = value.replace('[', '').replace(']', '').replace(
                    ' ', '').replace("'", '').split(',')
                for k in valuearray:
                    tempvalue.append(str(k))
                value = tempvalue
            else:
                value = list(value.replace('[', '').replace(']', '').split(','))
                value = [int(i) for i in value]
        elif value in 'true':
            value = bool(True)
        elif value in 'false':
            value = bool(False)
        elif value.isdigit():
            value = int(value)
        elif self.check_float(value):
            value = float(value)
        elif value == "None":
            value = None
        else:
            value = value.replace(' ', '_')
        return value

    @logger.catch
    @auth_required
    def set_device_walker(self):
        origin = request.form.get('origin')
        walker = request.form.get('walker')

        with open(self._args.mappings) as f:
            mapping = json.load(f)

        for key, val in enumerate(mapping["devices"]):
            device = mapping["devices"][key]

            if device["origin"] == origin:
                mapping["devices"][key]["walker"] = walker

        with open(self._args.mappings, 'w') as outfile:
            json.dump(mapping, outfile, indent=4, sort_keys=True)

        return "ok"

    @logger.catch
    @auth_required
    def settings_areas(self):
        with open(self._args.mappings) as f:
            mappings = json.load(f)

        areaname = request.args.get("name", None)

        if request.method == 'POST':
            for key, val in enumerate(mappings["areas"]):
                area = mappings["areas"][key]

                if area["name"] != areaname:
                    continue

                for entry in request.form:
                    value = request.form[entry]

                    if value == "None" or value == "":
                        value = None

                    if entry.startswith("field."):
                        name = entry.split("field.", 1)[1]
                        mappings["areas"][key][name] = value
                    else:
                        mappings["areas"][key]["settings"][entry] = value

            with open(self._args.mappings, 'w') as outfile:
                json.dump(mappings, outfile, indent=4, sort_keys=True)

            return redirect("/{}/settings/areas?name={}".format(self._args.madmin_base_path, areaname), code=302)

        if areaname is not None:
            areaconfig = None
            for key, val in enumerate(mappings["areas"]):
                tmparea = mappings["areas"][key]

                if tmparea["name"] == areaname:
                    areaconfig = tmparea

            with open('madmin/static/vars/vars_parser.json') as f:
                all_settings_vars = json.load(f)

            settings_vars = []
            for key, val in enumerate(all_settings_vars["areas"]):
                tmpsv = all_settings_vars["areas"][key]

                if tmpsv["name"] == areaconfig["mode"]:
                    settings_vars = tmpsv

            return render_template('settings_singlearea.html',
                                   area=areaconfig,
                                   subtab="areas",
                                   settings_vars=settings_vars)

        return render_template('settings_areas.html',
                               mappings=mappings,
                               subtab="areas")

    @logger.catch
    @auth_required
    def settings_devices(self):
        with open(self._args.mappings) as f:
            mappings = json.load(f)

        devicename = request.args.get("device", None)

        if request.method == 'POST':
            for key, val in enumerate(mappings["devices"]):
                device = mappings["devices"][key]

                if device["origin"] != devicename:
                    continue

                for entry in request.form:
                    value = request.form[entry]

                    if value == "None":
                        value = None

                    if entry.startswith("field."):
                        name = entry.split("field.", 1)[1]
                        mappings["devices"][key][name] = value
                    else:
                        mappings["devices"][key]["settings"][entry] = value

            with open(self._args.mappings, 'w') as outfile:
                json.dump(mappings, outfile, indent=4, sort_keys=True)

            return redirect("/{}/settings/devices?device={}".format(self._args.madmin_base_path, devicename), code=302)

        if devicename is not None:
            deviceconfig = None
            for key, val in enumerate(mappings["devices"]):
                tmpdevice = mappings["devices"][key]

                if tmpdevice["origin"] == devicename:
                    deviceconfig = tmpdevice

            with open('madmin/static/vars/vars_parser.json') as f:
                settings_vars = json.load(f)

            return render_template('settings_singledevice.html',
                                   deviceconfig=deviceconfig,
                                   subtab="devices",
                                   walker=mappings["walker"],
                                   pools=mappings["devicesettings"],
                                   settings_vars=settings_vars["devices"])

        return render_template('settings_devices.html',
                               mappings=mappings,
                               subtab="devices")

    @logger.catch
    @auth_required
    def settings_shared(self):
        with open(self._args.mappings) as f:
            mappings = json.load(f)

        sharedsettingname = request.args.get("setting", None)
        if request.method == 'POST':
            for key, val in enumerate(mappings["devicesettings"]):
                device = mappings["devicesettings"][key]

                if device["devicepool"] != sharedsettingname:
                    continue

                for entry in request.form:
                    value = request.form[entry]

                    if value == "None":
                        value = None

                    if entry.startswith("field."):
                        name = entry.split("field.", 1)[1]
                        mappings["devicesettings"][key][name] = value
                    else:
                        mappings["devicesettings"][key]["settings"][entry] = value

            with open(self._args.mappings, 'w') as outfile:
                json.dump(mappings, outfile, indent=4, sort_keys=True)

            return redirect("/{}/settings/shared?setting={}".format(self._args.madmin_base_path, sharedsettingname), code=302)

        if sharedsettingname is not None:
            sharedsetting = None
            for key, val in enumerate(mappings["devicesettings"]):
                tmpsetting = mappings["devicesettings"][key]

                if tmpsetting["devicepool"] == sharedsettingname:
                    sharedsetting = tmpsetting

            with open('madmin/static/vars/vars_parser.json') as f:
                settings_vars = json.load(f)

            return render_template("settings_singlesharedsetting.html",
                                   subtab="sharedsettings",
                                   settings_vars=settings_vars["devices"],
                                   sharedsetting=sharedsetting)

        return render_template("settings_sharedsettings.html",
                               subtab="sharedsettings",
                               mappings=mappings)

    @logger.catch
    @auth_required
    def settings(self):
        return redirect("/{}/settings/devices".format(self._args.madmin_base_path), code=302)

    @auth_required
    def addnew(self):
        area = request.args.get('area')
        line = ''
        with open('madmin/static/vars/vars_parser.json') as f:
            settings = json.load(f)
        if (len(settings[area])) == 1:
            return redirect(getBasePath(request) + '/config?type=' + area + '&area=' + area + '&block=fields', code=302)

        for output in settings[area]:
            line = line + '<h3><a href="config?type=' + str(output['name']) + '&area=' + str(
                area) + '&block=fields">' + str(output['name']) + '</a></h3><h5>' + str(
                output['description']) + '</h5><hr>'

        return render_template('sel_type.html', line=line, title="Type selector", running_ocr=(self._args.only_ocr))

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
        return redirect(getBasePath(request) + "/showsettings", code=302)

    def cmp_by_key(self, a, b, key):
           # RIP python2 cmp()
           return (a[key].lower() > b[key].lower()) - (a[key].lower() < b[key].lower())

    def sort_by_name_if_exists(self, a, b):
        # Sort areas by "name"
        if "name" in a and "name" in b:
            return self.cmp_by_key(a, b, "name")
        # Devices by origin
        elif "origin" in a and "origin" in b:
            return self.cmp_by_key(a, b, "origin")
        # Walkers by walkername
        elif "walkername" in a and "walkername" in b:
            return self.cmp_by_key(a, b, "walkername")
        # Global mon list by monlist
        elif "monlist" in a and "monlist" in b:
            return self.cmp_by_key(a, b, "monlist")
        # auth list by username
        elif "username" in a and "username" in b:
            return self.cmp_by_key(a, b, "username")
        # Leave rest unsorted
        else:
            return 0
