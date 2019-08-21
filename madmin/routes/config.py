import ast
import os
import json
import glob
from flask import (render_template, request, redirect)
from functools import cmp_to_key
from madmin.functions import auth_required, getBasePath
from utils.language import i8ln, open_json_file
from utils.adb import ADBConnect
from utils.MappingManager import MappingManager
from utils.logging import InterceptHandler, logger

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
        self._mapping_mananger = mapping_manager
        self.add_route()

    def add_route(self):
        routes = [
            ("/addwalker", self.addwalker),
            ("/savesortwalker", self.savesortwalker),
            ("/delwalker", self.delwalker),
            ("/config", self.config),
            ("/delsetting", self.delsetting),
            ("/addnew", self.addnew),
            ("/showmonsidpicker", self.showmonsidpicker),
            ("/addedit", self.addedit),
            ("/showsettings", self.showsettings),
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

        return render_template('parser.html', editform=fieldwebsite, header=header, title="edit settings")

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

    @logger.catch()
    @auth_required
    def config(self):
        fieldwebsite = []
        oldvalues = []
        sel = ''
        _walkernr = 0

        edit = False
        edit = request.args.get('edit')
        type = request.args.get('type')
        block = request.args.get('block')
        area = request.args.get('area')
        tabarea=area
        fieldwebsite.append('<form action="addedit" id="settings" method="post">')
        fieldwebsite.append(
            '<input type="hidden" name="block" value="' + block + '" />')
        fieldwebsite.append(
            '<input type="hidden" name="mode" value="' + type + '" />')
        fieldwebsite.append(
            '<input type="hidden" name="area" value="' + area + '" />')
        if edit:
            fieldwebsite.append(
                '<input type="hidden" name="edit" value="' + edit + '" />')
            with open(self._args.mappings) as f:
                mapping = json.load(f)
                if 'walker' not in mapping:
                    mapping['walker'] = []
                if 'devicesettings' not in mapping:
                    mapping['devicesettings'] = []
                nr = 0
                for oldfields in mapping[area]:
                    if 'name' in oldfields:
                        if oldfields['name'] == edit:
                            oldvalues = oldfields
                            _checkfield = 'name'
                    if 'origin' in oldfields:
                        if oldfields['origin'] == edit:
                            oldvalues = oldfields
                            _checkfield = 'origin'
                    if 'username' in oldfields:
                        if oldfields['username'] == edit:
                            oldvalues = oldfields
                            _checkfield = 'username'
                    if 'devicepool' in oldfields:
                        if oldfields['devicepool'] == edit:
                            oldvalues = oldfields
                            _checkfield = 'devicepool'
                    if 'monlist' in oldfields:
                        if oldfields['monlist'] == edit:
                            oldvalues = oldfields
                            _checkfield = 'monlist'
                    if 'walkername' in oldfields:
                        if oldfields['walkername'] == edit:
                            oldvalues = oldfields
                            _checkfield = 'walker'
                            _walkernr = nr
                        nr += 1

        with open('madmin/static/vars/vars_parser.json') as f:
            vars = json.load(f)

        for area in vars[area]:
            if 'name' in area:
                if area['name'] == type:
                    _name = area['name']
                    compfields = area
            if 'origin' in area:
                if area['origin'] == type:
                    _name = area['origin']
                    compfields = area
            if 'username' in area:
                if area['username'] == type:
                    _name = area['username']
                    compfields = area
            if 'walker' in area:
                if area['walker'] == type:
                    _name = area['walker']
                    compfields = area
            if 'devicesettings' in area:
                if area['devicesettings'] == type:
                    _name = area['devicesettings']
                    compfields = area
            if 'monivlist' in area:
                if area['monivlist'] == type:
                    _name = area['monivlist']
                    compfields = area

        for field in compfields[block]:
            lock = field['settings'].get("lockonedit", False)
            showmonsidpicker = field['settings'].get("showmonsidpicker", False)
            lockvalue = 'readonly' if lock and edit else ''
            req = 'required' if field['settings'].get(
                'require', 'false') == 'true' else ''
            if field['settings']['type'] == 'text' or field['settings']['type'] == 'textarea':
                val = ''
                if edit:
                    if block == 'settings':
                        if field['name'] in oldvalues['settings'] and str(oldvalues['settings'][field['name']]) != str(
                                'None'):
                            val = str(oldvalues['settings'][field['name']])
                    else:
                        if field['name'] in oldvalues and str(oldvalues[field['name']]) != str('None'):
                            val = str(oldvalues[field['name']])

                formStr = '<div class="form-group">'
                formStr += '<label>' + str(field['name']) + '</label><br /><small class="form-text text-muted">' + str(
                    field['settings']['description']) + '</small>'

                # No idea how/where to put that link, ended with this one
                if showmonsidpicker:
                    monsidpicker_link = '<a href=showmonsidpicker?edit=' + str(edit) + '&type=' + str(
                        type) + '>[BETA ID Picker]</a>'
                    formStr += monsidpicker_link
                if field['settings']['type'] == 'text':
                    formStr += '<input type="text" name="' + \
                               str(field['name']) + '" value="' + val + \
                               '" ' + lockvalue + ' ' + req + '>'
                if field['settings']['type'] == 'textarea':
                    formStr += '<textarea rows="10" name="' + \
                               str(field['name']) + '" ' + lockvalue + \
                               ' ' + req + '>' + val + '</textarea>'
                formStr += '</div>'
                fieldwebsite.append(formStr)

            if field['settings']['type'] == 'list':
                if edit:
                    val = ''
                    fieldwebsite.append('<div class="form-group"><label>' + str(
                        field['name']) + '</label><br /><small class="form-text text-muted">' + str(
                        field['settings']['description']) + '</small></div>')

                    fieldwebsite.append('<table class="table">')
                    fieldwebsite.append(
                        '<tr><th></th><th>Nr.</th><th>Area<br>Description</th><th>Walkermode</th><th>Setting</th>'
                        '<th>Max. Devices</th><th></th></tr><tbody class="row_position">')
                    if block != 'settings':
                        if field['name'] in oldvalues and str(oldvalues[field['name']]) != str('None'):
                            val = list(oldvalues[field['name']])
                            i = 0
                            while i < len(val):
                                fieldwebsite.append('<tr id=' + str(val[i]['walkerarea']) + '|' + str(
                                    val[i]['walkertype']) + '|' + str(val[i]['walkervalue']) + '|' + str(
                                    val[i].get('walkermax', '')) + '|' + str(val[i].get('walkertext', '')).replace(' ',
                                                                                                                   '_') + '>'
                                                                                                                          '<td ><img src="static/sort.png" class="handle"></td><td>' + str(
                                    i) + '</td><td><b>' + str(val[i]['walkerarea']) + '</b><br>' + str(
                                    val[i].get('walkertext', '')).replace('_', ' ') + '</td><td>' + str(
                                    val[i]['walkertype']) + '</td><td>' + str(
                                    val[i]['walkervalue']) + '</td><td>' + str(
                                    val[i].get('walkermax', '')) + '</td><td>'
                                                                   '<a href="delwalker?walker=' + str(
                                    edit) + '&walkernr=' + str(
                                    _walkernr) + '&walkerposition=' + str(i) + '" class="confirm" '\
                                                                               'title="Do you really want to delete '
                                                                               'this?">'\
                                                                               'Delete</a><br>'
                                                                               '<a href="addwalker?walker=' + str(
                                    edit) + '&walkernr=' + str(_walkernr) + '&walkerposition=' + str(
                                    i) + '&edit=True">Edit</a></form></td></tr>')
                                i += 1

                        fieldwebsite.append('</tbody></table>')
                        fieldwebsite.append(
                            '<div class="form-group"><a href="addwalker?walker=' + str(edit) + '&walkernr=' + str(
                                _walkernr) + '">Add Area</a></div>')

            if field['settings']['type'] == 'option':
                _temp = '<div class="form-group"><label>' + str(
                    field['name']) + '</label><br /><small class="form-text text-muted">' + str(
                    field['settings']['description']) + '</small><select class="form-control" name="' + str(
                    field['name']) + '" ' + lockvalue + ' ' + req + '>'
                _options = field['settings']['values'].split('|')
                for option in _options:
                    if edit:
                        if block == 'settings':
                            if field['name'] in oldvalues['settings']:
                                if str(oldvalues['settings'][field['name']]).lower() in str(option).lower():
                                    sel = 'selected'
                        else:
                            if field['name'] in oldvalues:
                                if str(oldvalues[field['name']]).lower() in str(option).lower():
                                    sel = 'selected'
                    _temp = _temp + '<option value="' + \
                            str(option) + '" ' + sel + '>' + str(option) + '</option>'
                    sel = ''
                _temp = _temp + '</select></div>'
                fieldwebsite.append(str(_temp))

            if field['settings']['type'] == 'areaselect':
                _temp = '<div class="form-group"><label>' + str(
                    field['name']) + '</label><br /><small class="form-text text-muted">' + str(
                    field['settings']['description']) + '</small><select class="form-control" name="' + str(
                    field['name']) + '" ' + lockvalue + ' ' + req + '>'
                with open(self._args.mappings) as f:
                    mapping = json.load(f)
                    if 'walker' not in mapping:
                        mapping['walker'] = []
                mapping['areas'].append({'name': None})

                for option in mapping['areas']:
                    if edit:
                        if block == "settings":
                            if str(oldvalues[field['settings']['name']]).lower() == str(option['name']).lower():
                                sel = 'selected'
                            else:
                                if oldvalues[field['settings']['name']] == '':
                                    sel = 'selected'
                        else:
                            if field['name'] in oldvalues:
                                if str(oldvalues[field['name']]).lower() == str(option['name']).lower():
                                    sel = 'selected'
                            else:
                                if not option['name']:
                                    sel = 'selected'
                    _temp = _temp + '<option value="' + \
                            str(option['name']) + '" ' + sel + '>' + \
                            str(option['name']) + '</option>'
                    sel = ''
                _temp = _temp + '</select></div>'
                fieldwebsite.append(str(_temp))

            if field['settings']['type'] == 'adbselect':
                devices = self._adb_connect.return_adb_devices()
                _temp = '<div class="form-group"><label>' + str(
                    field['name']) + '</label><br /><small class="form-text text-muted">' + str(
                    field['settings']['description']) + '</small><select class="form-control" name="' + str(
                    field['name']) + '" ' + lockvalue + ' ' + req + '>'
                adb = {}
                adb['serial'] = []
                adb['serial'].append({'name': None})
                for device in devices:
                    adb['serial'].append({'name': device.serial})

                for option in adb['serial']:
                    if edit:
                        if block == "settings":
                            if str(oldvalues[field['settings']['name']]).lower() == str(option['name']).lower():
                                sel = 'selected'
                            else:
                                if oldvalues[field['settings']['name']] == '':
                                    sel = 'selected'
                        else:
                            if field['name'] in oldvalues:
                                if str(oldvalues[field['name']]).lower() == str(option['name']).lower():
                                    sel = 'selected'
                            else:
                                if not option['name']:
                                    sel = 'selected'
                    _temp = _temp + '<option value="' + \
                            str(option['name']) + '" ' + sel + '>' + \
                            str(option['name']) + '</option>'
                    sel = ''
                _temp = _temp + '</select></div>'
                fieldwebsite.append(str(_temp))

            if field['settings']['type'] == 'walkerselect':
                _temp = '<div class="form-group"><label>' + str(
                    field['name']) + '</label><br /><small class="form-text text-muted">' + str(
                    field['settings']['description']) + '</small><select class="form-control" name="' + str(
                    field['name']) + '" ' + lockvalue + ' ' + req + '>'
                with open(self._args.mappings) as f:
                    mapping = json.load(f)
                    if 'walker' not in mapping:
                        mapping['walker'] = []
                for option in mapping['walker']:
                    if edit:
                        if field['name'] in oldvalues:
                            if str(oldvalues[field['name']]).lower() == str(option['walkername']).lower():
                                sel = 'selected'
                        else:
                            if not option['walkername']:
                                sel = 'selected'
                    _temp = _temp + '<option value="' + \
                            str(option['walkername']) + '" ' + sel + '>' + \
                            str(option['walkername']) + '</option>'
                    sel = ''
                _temp = _temp + '</select></div>'
                fieldwebsite.append(str(_temp))

            if field['settings']['type'] == 'monlistselect':
                _temp = '<div class="form-group"><label>' + str(
                    field['name']) + '</label><br /><small class="form-text text-muted">' + str(
                    field['settings']['description']) + '</small><select class="form-control" name="' + str(
                    field['name']) + '" ' + lockvalue + ' ' + req + '>'
                temp_mapping = {}
                temp_mapping['monivlist'] = []
                with open(self._args.mappings) as f:
                    mapping = json.load(f)
                    if 'monivlist' not in mapping:
                        mapping['monivlist'] = []
                temp_mapping['monivlist'].append({'monlist': None})
                for monlist_temp in mapping['monivlist']:
                    temp_mapping['monivlist'].append({'monlist': monlist_temp['monlist']})
                for option in temp_mapping['monivlist']:
                    if edit:
                        if field['name'] in oldvalues['settings']:
                            if str(oldvalues['settings'][field['name']]).lower() == str(option['monlist']).lower():
                                sel = 'selected'
                        else:
                            if not option['monlist']:
                                sel = 'selected'
                    _temp = _temp + '<option value="' + \
                            str(option['monlist']) + '" ' + sel + '>' + \
                            str(option['monlist']) + '</option>'
                    sel = ''
                _temp = _temp + '</select></div>'
                fieldwebsite.append(str(_temp))

            if field['settings']['type'] == 'fenceselect':
                _temp = '<div class="form-group"><label>' + str(
                    field['name']) + '</label><br /><small class="form-text text-muted">' + str(
                    field['settings']['description']) + '</small><select class="form-control" name="' + str(
                    field['name']) + '" ' + lockvalue + ' ' + req + '>'
                temp_mapping = {}
                temp_mapping['fence'] = []
                geofence_file_path = self._args.geofence_file_path
                existing_fences = glob.glob(os.path.join(geofence_file_path, '*.txt'))
                temp_mapping['fence'].append({'fence': None, 'realpath': None})
                for geofence_temp in existing_fences:
                    temp_mapping['fence'].append({'fence': os.path.basename(geofence_temp),
                                                  'realpath': geofence_temp})

                for option in temp_mapping['fence']:
                    if edit:
                        if field['name'] in oldvalues:
                            if os.path.basename(str(oldvalues[field['name']])).lower() == \
                                    os.path.basename(str(option['fence'])).lower():
                                sel = 'selected'
                        else:
                            if not option['fence']:
                                sel = 'selected'
                    _temp = _temp + '<option value="' + \
                            str(option['realpath']) + '" ' + sel + '>' + \
                            os.path.splitext(str(option['fence']))[0] + '</option>'
                    sel = ''
                _temp = _temp + '</select></div>'
                fieldwebsite.append(str(_temp))

            if field['settings']['type'] == 'poolselect':
                _temp = '<div class="form-group"><label>' + str(
                    field['name']) + '</label><br /><small class="form-text text-muted">' + str(
                    field['settings']['description']) + '</small><select class="form-control" name="' + str(
                    field['name']) + '" ' + lockvalue + ' ' + req + '>'
                with open(self._args.mappings) as f:
                    mapping = json.load(f)
                    if 'devicesettings' not in mapping:
                        mapping['devicesettings'] = []
                mapping['devicesettings'].append({'devicepool': None})
                for option in mapping['devicesettings']:
                    if edit:
                        if field['name'] in oldvalues:
                            if str(oldvalues[field['name']]).lower() == str(option['devicepool']).lower():
                                sel = 'selected'
                        else:
                            if not option['devicepool']:
                                sel = 'selected'
                    _temp = _temp + '<option value="' + \
                            str(option['devicepool']) + '" ' + sel + '>' + \
                            str(option['devicepool']) + '</option>'
                    sel = ''
                _temp = _temp + '</select></div>'
                fieldwebsite.append(str(_temp))

            if field['settings']['type'] == 'areaoption':
                _temp = '<div class="form-group"><label>' + str(
                    field['name']) + '</label><br /><small class="form-text text-muted">' + str(
                    field['settings']['description']) + '</small><select class="form-control" name="' + str(
                    field['name']) + '" ' + lockvalue + ' ' + req + ' size=10 multiple=multiple>'
                with open(self._args.mappings) as f:
                    mapping = json.load(f)
                    if 'walker' not in mapping:
                        mapping['walker'] = []
                mapping['areas'].append({'name': None})
                oldvalues_split = []

                if edit:
                    if block == "settings":
                        if oldvalues[field['settings']['name']] is not None:
                            oldvalues_split = oldvalues[field['settings']['name']].replace(
                                " ", "").split(",")
                    else:
                        if oldvalues[field['name']] is not None:
                            oldvalues_split = oldvalues[field['name']].replace(
                                " ", "").split(",")

                for option in mapping['areas']:
                    if edit:
                        for old_value in oldvalues_split:
                            if block == "settings":
                                if str(old_value).lower() == str(option['name']).lower():
                                    sel = 'selected'
                                else:
                                    if old_value == '':
                                        sel = 'selected'
                            else:
                                if field['name'] in oldvalues:
                                    if str(old_value).lower() == str(option['name']).lower():
                                        sel = 'selected'
                                else:
                                    if not option['name']:
                                        sel = 'selected'
                    _temp = _temp + '<option value="' + \
                            str(option['name']) + '" ' + sel + '>' + \
                            str(option['name']) + '</option>'
                    sel = ''
                _temp = _temp + '</select></div>'
                fieldwebsite.append(str(_temp))

        if edit:
            header = "Edit " + edit + " (" + type + ")"
        else:
            header = "Add new " + type

        if (type == 'walker' and edit is None) or (type != 'walker' and edit is not None) \
                or (type != 'walker' and edit is None):
            fieldwebsite.append(
                '<button type="submit" class="btn btn-primary">Save</button></form>')

        return render_template('parser.html', editform=fieldwebsite, header=header, title="edit settings",
                               walkernr=_walkernr, edit=edit, tabarea=tabarea)

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
    def showsettings(self):
        tab_content = ''
        tabarea = request.args.get("area", 'devices')
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
        with open('madmin/static/vars/vars_parser.json') as f:
            vars = json.load(f)

        globalheader = '<thead><tr><th><b>Type</b></th><th>Basedata</th><th>Settings</th><th>Delete</th></tr></thead>'

        for var in vars:
            line, quickadd, quickline = '', '', ''
            header = '<tr><td colspan="4" class="header"><b>' + (var.upper()) + '</b> <a href="addnew?area=' + var + \
                     '">[Add new]</a></td><td style="display: none;"></td><td style="display: none;"></td><td style="display: none;"></td></tr>'
            subheader = '<tr><td colspan="4">' + \
                        settings[var]['description'] + \
                        '</td><td style="display: none;"></td><td style="display: none;"></td><td style="display: none;"></td></tr>'
            edit = '<td></td>'
            editsettings = '<td></td>'
            _typearea = var
            _field = settings[var]['field']
            _quick = settings[var].get('quickview', False)
            _quicksett = settings[var].get('quickview_settings', False)

            for output in sorted(mapping[var], key=cmp_to_key(self.sort_by_name_if_exists)):
                quickadd, quickline = '', ''
                mode = output.get('mode', _typearea)
                if settings[var]['could_edit']:
                    edit = '<td><a href="config?type=' + str(mode) + '&area=' + str(
                        _typearea) + '&block=fields&edit=' + str(output[_field]) + '">[Edit]</a></td>'
                else:
                    edit = '<td></td>'
                if settings[var]['has_settings'] in ('true'):
                    editsettings = '<td><a href="config?type=' + str(mode) + '&area=' + str(
                        _typearea) + '&block=settings&edit=' + str(output[_field]) + '">[Edit Settings]</a></td>'
                else:
                    editsettings = '<td></td>'
                delete = '<td><a href="delsetting?type=' + str(mode) + '&area=' + str(
                    _typearea) + '&block=settings&edit=' + str(output[_field]) + '&del=true" class="confirm" ' \
                                                                                 'title="Do you really want to delete this?">' \
                                                                                 '[Delete]</a></td>'

                line = line + '<tr><td><b>' + \
                       str(output[_field]) + '</b></td>' + str(edit) + \
                       str(editsettings) + str(delete) + '</tr>'

                if _quick == 'setup':
                    quickadd = 'Assigned areas: ' + \
                               str(len(output.get('setup', []))) + '<br />Areas: '
                    for area in output.get('setup', []):
                        quickadd = quickadd + area.get('walkerarea') + ' | '

                    quickline = quickline + '<tr><td></td><td colspan="3" class="quick">' + \
                                str(
                                    quickadd) + ' </td><td style="display: none;"></td><td style="display: none;">' \
                                                '</td><td style="display: none;"></td>'

                elif _quick:
                    for quickfield in _quick.split('|'):
                        if output.get(quickfield, False):
                            quickadd = quickadd + \
                                       str(quickfield) + ': ' + \
                                       str(output.get(quickfield, '')).split(
                                           '\n')[0] + '<br>'
                    quickline = quickline + '<tr><td></td><td class="quick">' + \
                                str(quickadd) + '</td>'

                quickadd = ''
                if _quicksett:
                    for quickfield in _quicksett.split('|'):
                        if output['settings'].get(quickfield, False):
                            quickadd = quickadd + \
                                       str(quickfield) + ': ' + \
                                       str(output['settings'].get(
                                           quickfield, '')) + '<br>'
                    quickline = quickline + '<td colspan="2" class="quick">' + \
                                str(quickadd) + '</td><td style="display: none;"></td></tr>'

                line = line + quickline

            if str(tabarea) == str(var):
                _active = 'show active'
            else:
                _active = ""

            _tab_starter = '<div class="tab-pane fade ' + str(_active) + '"  id="nav-' + str(var) \
                           + '" role="tabpanel" aria-labelledby="nav-' + str(var) + '-tab">'

            table = str(_tab_starter) + '<table>' + str(globalheader) + '<tbody>' + str(header) + str(subheader) + str(line) \
                     + '</tbody></table></div>'

            tab_content = tab_content + table

        return render_template('settings.html',
                               settings=tab_content,
                               tabarea=tabarea,
                               title="Mapping Editor", responsive=str(self._args.madmin_noresponsive).lower(),
                               autoreloadconfig=self._args.auto_reload_config)

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
        return render_template('sel_type.html', line=line, title="Type selector")

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
            # force single 'string' value to tuple. Not pretty, but it works.
            mapping["monivlist"][this_area_index]["mon_ids_iv"] = ast.literal_eval(new_mons_list+",")

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
