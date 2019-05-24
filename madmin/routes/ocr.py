import os
import glob
import json
import re
import datetime
from flask import (jsonify, request, redirect, render_template)
from utils.functions import (creation_date)
from utils.language import i8ln, open_json_file
from madmin.functions import auth_required, getBasePath, decodeHashJson, encodeHashJson, getAllHash
from shutil import copyfile


class ocr(object):
    def __init__(self, db, args, logger, app):
        self._db = db
        self._args = args
        self._app = app
        if self._args.madmin_time == "12":
            self._datetimeformat = '%Y-%m-%d %I:%M:%S %p'
        else:
            self._datetimeformat = '%Y-%m-%d %H:%M:%S'
        self._logger = logger
        self.add_route()

    def add_route(self):
        routes = [
            ("/submit_hash", self.submit_hash),
            ("/modify_raid_gym", self.modify_raid_gym),
            ("/modify_raid_mon", self.modify_raid_mon),
            ("/modify_gym_hash", self.modify_gym_hash),
            ("/near_gym", self.near_gym),
            ("/delete_hash", self.delete_hash),
            ("/delete_file", self.delete_file),
            ("/get_gyms", self.get_gyms),
            ("/get_raids", self.get_raids),
            ("/get_mons", self.get_mons),
            ("/get_screens", self.get_screens),
            ("/get_unknowns", self.get_unknowns),
            ("/match_unknowns", self.match_unknowns),
            ("/modify_raid", self.modify_raid),
            ("/modify_gym", self.modify_gym),
            ("/modify_mon", self.modify_mon)
        ]
        for route, view_func in routes:
            self._app.route(route)(view_func)

    @auth_required
    def submit_hash(self):
        hash = request.args.get('hash')
        id = request.args.get('id')

        if self._db.insert_hash(hash, 'gym', id, '999', unique_hash="madmin"):

            for file in glob.glob("www_hash/unkgym_*" + str(hash) + ".jpg"):
                copyfile(file, 'www_hash/gym_0_0_' + str(hash) + '.jpg')
                os.remove(file)

            return redirect(getBasePath(request) + "/unknown", code=302)

    @auth_required
    def modify_raid_gym(self):
        hash = request.args.get('hash')
        id = request.args.get('id')
        mon = request.args.get('mon')
        lvl = request.args.get('lvl')

        newJsonString = encodeHashJson(id, lvl, mon)
        self._db.delete_hash_table(str(hash), 'raid', 'in', 'hash')
        self._db.insert_hash(hash, 'raid', newJsonString,
                               '999', unique_hash="madmin")

        return redirect(getBasePath(request) + "/raids", code=302)

    @auth_required
    def modify_raid_mon(self):
        hash = request.args.get('hash')
        id = request.args.get('gym')
        mon = request.args.get('mon')
        lvl = request.args.get('lvl')

        newJsonString = encodeHashJson(id, lvl, mon)
        self._db.delete_hash_table(str(hash), 'raid', 'in', 'hash')
        self._db.insert_hash(hash, 'raid', newJsonString,
                               '999', unique_hash="madmin")

        return redirect(getBasePath(request) + "/raids", code=302)

    @auth_required
    def modify_gym_hash(self):
        hash = request.args.get('hash')
        id = request.args.get('id')

        self._db.delete_hash_table(str(hash), 'gym', 'in', 'hash')
        self._db.insert_hash(hash, 'gym', id, '999', unique_hash="madmin")

        return redirect(getBasePath(request) + "/gyms", code=302)

    @auth_required
    def near_gym(self):
        nearGym = []

        data = self._db.get_gym_infos()

        lat = request.args.get('lat')
        lon = request.args.get('lon')
        if lat == "9999":
            distance = int(9999)
            lat = self._args.home_lat
            lon = self._args.home_lng
        else:
            distance = int(self._args.unknown_gym_distance)

        if not lat or not lon:
            return 'Missing Argument...'
        closestGymIds = self._db.get_near_gyms(
            lat, lon, 123, 1, int(distance), unique_hash="madmin")
        for closegym in closestGymIds:

            gymid = str(closegym[0])
            dist = str(closegym[1])
            gymImage = 'gym_img/_' + str(gymid) + '_.jpg'
            name = 'unknown'
            lat = '0'
            lon = '0'
            description = ''

            if str(gymid) in data:
                name = data[str(gymid)]["name"].replace(
                    "\\", r"\\").replace('"', '')
                lat = data[str(gymid)]["latitude"]
                lon = data[str(gymid)]["longitude"]
                if data[str(gymid)]["description"]:
                    description = data[str(gymid)]["description"].replace(
                        "\\", r"\\").replace('"', '').replace("\n", "")

            ngjson = ({'id': gymid, 'dist': dist, 'name': name, 'lat': lat, 'lon': lon,
                       'description': description, 'filename': gymImage})
            nearGym.append(ngjson)

        return jsonify(nearGym)

    @auth_required
    def delete_hash(self):
        hash = request.args.get('hash')
        type = request.args.get('type')
        redi = request.args.get('redirect')
        if not hash or not type:
            return 'Missing Argument...'

        self._db.delete_hash_table(str(hash), type, 'in', 'hash')
        for file in glob.glob("ocr/www_hash/*" + str(hash) + ".jpg"):
            os.remove(file)

        return redirect(getBasePath(request) + '/' + str(redi), code=302)

    @auth_required
    def delete_file(self):
        hash = request.args.get('hash')
        type = request.args.get('type')
        redi = request.args.get('redirect')
        if not hash or not type:
            return 'Missing Argument...'

        for file in glob.glob("ocr/www_hash/*" + str(hash) + ".jpg"):
            os.remove(file)

        return redirect(getBasePath(request) + '/' + str(redi), code=302)

    @auth_required
    def get_gyms(self):
        gyms = []
        data = self._db.get_gym_infos()

        hashdata = json.loads(getAllHash('gym', self._db))

        for file in glob.glob("ocr/www_hash/gym_*.jpg"):
            unkfile = re.search(r'gym_(-?\d+)_(-?\d+)_((?s).*)\.jpg', file)
            hashvalue = (unkfile.group(3))

            if str(hashvalue) in hashdata:

                gymid = hashdata[str(hashvalue)]["id"]
                count = hashdata[hashvalue]["count"]
                modify = hashdata[hashvalue]["modify"]

                creationdate = datetime.datetime.fromtimestamp(
                    creation_date(file)).strftime(self._datetimeformat)

                modify = datetime.datetime.strptime(
                    modify, '%Y-%m-%d %H:%M:%S').strftime(self._datetimeformat)

                name = 'unknown'
                lat = '0'
                lon = '0'
                description = ''

                gymImage = 'gym_img/_' + str(gymid) + '_.jpg'

                if str(gymid) in data:
                    name = data[str(gymid)]["name"].replace(
                        "\\", r"\\").replace('"', '')
                    lat = data[str(gymid)]["latitude"]
                    lon = data[str(gymid)]["longitude"]
                    if data[str(gymid)]["description"]:
                        description = data[str(gymid)]["description"].replace(
                            "\\", r"\\").replace('"', '').replace("\n", "")

                gymJson = ({'id': gymid, 'lat': lat, 'lon': lon, 'hashvalue': hashvalue,
                            'filename': file[4:], 'name': name, 'description': description,
                            'gymimage': gymImage, 'count': count, 'creation': creationdate, 'modify': modify})
                gyms.append(gymJson)

            else:
                self.logger.debug("File: " + str(file) + " not found in Database")
                os.remove(str(file))
                continue

        return jsonify(gyms)

    @auth_required
    def get_raids(self):
        raids = []
        eggIdsByLevel = [1, 1, 2, 2, 3]

        data = self._db.get_gym_infos()

        mondata = open_json_file('pokemon')

        hashdata = json.loads(getAllHash('raid', self._db))

        for file in glob.glob("ocr/www_hash/raid_*.jpg"):
            unkfile = re.search(r'raid_(-?\d+)_(-?\d+)_((?s).*)\.jpg', file)
            hashvalue = (unkfile.group(3))

            if str(hashvalue) in hashdata:
                monName = 'unknown'
                raidjson = hashdata[str(hashvalue)]["id"]
                count = hashdata[hashvalue]["count"]
                modify = hashdata[hashvalue]["modify"]

                raidHash_ = decodeHashJson(raidjson)
                gymid = raidHash_[0]
                lvl = raidHash_[1]
                mon = int(raidHash_[2])
                monid = int(raidHash_[2])
                mon = "%03d" % mon

                if mon == '000':
                    type = 'egg'
                    monPic = ''
                else:
                    type = 'mon'
                    monPic = 'asset/pokemon_icons/pokemon_icon_' + mon + '_00.png'
                    if str(monid) in mondata:
                        monName = i8ln(mondata[str(monid)]["name"])

                eggId = eggIdsByLevel[int(lvl) - 1]
                if eggId == 1:
                    eggPic = 'asset/static_assets/png/ic_raid_egg_normal.png'
                if eggId == 2:
                    eggPic = 'asset/static_assets/png/ic_raid_egg_rare.png'
                if eggId == 3:
                    eggPic = 'asset/static_assets/png/ic_raid_egg_legendary.png'

                creationdate = datetime.datetime.fromtimestamp(
                    creation_date(file)).strftime(self._datetimeformat)

                modify = datetime.datetime.strptime(
                    modify, '%Y-%m-%d %H:%M:%S').strftime(self._datetimeformat)

                name = 'unknown'
                lat = '0'
                lon = '0'
                description = ''

                gymImage = 'gym_img/_' + str(gymid) + '_.jpg'

                if str(gymid) in data:
                    name = data[str(gymid)]["name"].replace(
                        "\\", r"\\").replace('"', '')
                    lat = data[str(gymid)]["latitude"]
                    lon = data[str(gymid)]["longitude"]
                    if data[str(gymid)]["description"]:
                        description = data[str(gymid)]["description"].replace(
                            "\\", r"\\").replace('"', '').replace("\n", "")

                raidJson = ({'id': gymid, 'lat': lat, 'lon': lon, 'hashvalue': hashvalue, 'filename': file[4:],
                             'name': name, 'description': description, 'gymimage': gymImage,
                             'count': count, 'creation': creationdate, 'modify': modify, 'level': lvl,
                             'mon': mon, 'type': type, 'eggPic': eggPic, 'monPic': monPic, 'monname': monName})
                raids.append(raidJson)
            else:
                self._logger.debug("File: " + str(file) + " not found in Database")
                os.remove(str(file))
                continue

        return jsonify(raids)

    @auth_required
    def get_mons(self):
        mons = []
        monList = []

        mondata = open_json_file('pokemon')

        with open('raidmons.json') as f:
            raidmon = json.load(f)

        for mons in raidmon:
            for mon in mons['DexID']:
                lvl = mons['Level']
                if str(mon).find("_") > -1:
                    mon_split = str(mon).split("_")
                    mon = mon_split[0]
                    frmadd = mon_split[1]
                else:
                    frmadd = "00"

                mon = '{:03d}'.format(int(mon))

                monPic = 'asset/pokemon_icons/pokemon_icon_' + mon + '_' + frmadd + '.png'
                monName = 'unknown'
                monid = int(mon)

                if str(monid) in mondata:
                    monName = i8ln(mondata[str(monid)]["name"])

                monJson = ({'filename': monPic, 'mon': monid,
                            'name': monName, 'lvl': lvl})
                monList.append(monJson)

        return jsonify(monList)

    @auth_required
    def get_screens(self):
        screens = []

        for file in glob.glob(str(self._args.raidscreen_path) + "/raidscreen_*.png"):
            creationdate = datetime.datetime.fromtimestamp(
                creation_date(file)).strftime(self._datetimeformat)

            screenJson = ({'filename': file[4:], 'creation': creationdate})
            screens.append(screenJson)

        return jsonify(screens)

    @auth_required
    def get_unknowns(self):
        unk = []
        for file in glob.glob("ocr/www_hash/unkgym_*.jpg"):
            unkfile = re.search(
                r'unkgym_(-?\d+\.?\d+)_(-?\d+\.?\d+)_((?s).*)\.jpg', file)
            creationdate = datetime.datetime.fromtimestamp(
                creation_date(file)).strftime(self._datetimeformat)
            lat = (unkfile.group(1))
            lon = (unkfile.group(2))
            hashvalue = (unkfile.group(3))

            hashJson = ({'lat': lat, 'lon': lon, 'hashvalue': hashvalue,
                         'filename': file[4:], 'creation': creationdate})
            unk.append(hashJson)

        return jsonify(unk)

    @auth_required
    def match_unknowns(self):
        hash = request.args.get('hash')
        lat = request.args.get('lat')
        lon = request.args.get('lon')
        return render_template('match_unknown.html', hash=hash, lat=lat, lon=lon,
                               responsive=str(self._args.madmin_noresponsive).lower(), title="match Unknown",
                               running_ocr=(self._args.only_ocr))

    @auth_required
    def modify_raid(self):
        hash = request.args.get('hash')
        lat = request.args.get('lat')
        lon = request.args.get('lon')
        lvl = request.args.get('lvl')
        mon = request.args.get('mon')
        return render_template('change_raid.html', hash=hash, lat=lat, lon=lon, lvl=lvl, mon=mon,
                               responsive=str(self._args.madmin_noresponsive).lower(), title="change Raid",
                               running_ocr=(self._args.only_ocr))

    @auth_required
    def modify_gym(self):
        hash = request.args.get('hash')
        lat = request.args.get('lat')
        lon = request.args.get('lon')
        return render_template('change_gym.html', hash=hash, lat=lat, lon=lon,
                               responsive=str(self._args.madmin_noresponsive).lower(), title="change Gym",
                               running_ocr=(self._args.only_ocr))

    @auth_required
    def modify_mon(self):
        hash = request.args.get('hash')
        gym = request.args.get('gym')
        lvl = request.args.get('lvl')
        return render_template('change_mon.html', hash=hash, gym=gym, lvl=lvl,
                               responsive=str(self._args.madmin_noresponsive).lower(), title="change Mon",
                               running_ocr=(self._args.only_ocr))
