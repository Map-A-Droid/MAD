# -*- coding: utf-8 -*-
import datetime
import glob
import json
import os
import re
import sys
import threading
import time
from functools import update_wrapper, wraps
from math import floor
from pathlib import Path
from shutil import copyfile

from flask import (Flask, jsonify, make_response, redirect, render_template,
                   request, send_from_directory)
from gevent.pywsgi import WSGIServer

import cv2
from flask_caching import Cache
from utils.adb import ADBConnect
from utils.functions import (creation_date, generate_path, generate_phones,
                             image_resize)
from utils.language import i8ln, open_json_file
from utils.logging import LogLevelChanger, logger
from utils.mappingParser import MappingParser
from utils.questGen import generate_quest

sys.path.append("..")  # Adds higher directory to python modules path.


app = Flask(__name__)
cache = Cache(app, config={'CACHE_TYPE': 'simple'})
log = logger
conf_args = None
db_wrapper = None
device_mappings = None
areas = None
ws_server = None
datetimeformat = None
adb_connect = None


def madmin_start(arg_args, arg_db_wrapper, glob_ws_server):
    global conf_args, device_mappings, db_wrapper, areas, ws_server, datetimeformat, adb_connect
    conf_args = arg_args
    db_wrapper = arg_db_wrapper
    mapping_parser = MappingParser(db_wrapper, conf_args)
    device_mappings = mapping_parser.get_devicemappings()
    areas = mapping_parser.get_areas()
    ws_server = glob_ws_server
    adb_connect = ADBConnect(conf_args)
    if conf_args.madmin_time == "12":
        datetimeformat = '%Y-%m-%d %I:%M:%S %p'
    else:
        datetimeformat = '%Y-%m-%d %H:%M:%S'

    httpsrv = WSGIServer((arg_args.madmin_ip, int(
        arg_args.madmin_port)), app.wsgi_app, log=LogLevelChanger)
    httpsrv.serve_forever()


def auth_required(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        username = getattr(conf_args, 'madmin_user', '')
        password = getattr(conf_args, 'madmin_password', '')
        if not username:
            return func(*args, **kwargs)
        if request.authorization:
            if (request.authorization.username == username) and (
                    request.authorization.password == password):
                return func(*args, **kwargs)
        return make_response('Could not verify!', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})

    return decorated


def run_job():
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        exit(0)

    t_webApp = threading.Thread(name='Web App', target=run_job)
    t_webApp.setDaemon(True)
    t_webApp.start()


def nocache(view):
    @wraps(view)
    def no_cache(*args, **kwargs):
        response = make_response(view(*args, **kwargs))
        response.headers['Last-Modified'] = datetime.datetime.now()
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
        return response

    return update_wrapper(no_cache, view)


@app.after_request
@auth_required
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers',
                         'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods',
                         'GET,PUT,POST,DELETE,OPTIONS')
    return response


@app.route('/phonecontrol', methods=['GET'])
@auth_required
@nocache
def get_phonescreens():
    if not os.path.exists(os.path.join(conf_args.temp_path, "madmin")):
        os.makedirs(os.path.join(conf_args.temp_path, "madmin"))
    global device_mappings
    global ws_server

    screens_phone = []
    ws_connected_phones = []
    if ws_server is not None:
        phones = ws_server.get_reg_origins().copy()
    else:
        phones = []
    for phonename in phones:
        ws_connected_phones.append(phonename)
        add_text = ""
        adb_option = False
        adb = device_mappings[phonename].get('adb', False)
        if adb is not None and adb_connect.check_adb_status(adb) is not None:
            ws_connected_phones.append(adb)
            adb_option = True
            add_text = '<b>ADB</b>'
        else:
            ws_connected_phones.append(adb)

        filename = os.path.join(conf_args.temp_path,
                                'screenshot%s.png' % str(phonename))
        if os.path.isfile(filename):
            image_resize(filename, os.path.join(
                conf_args.temp_path, "madmin"), width=200)
            screen = "/screenshot/madmin/screenshot" + str(phonename) + ".png"
            screens_phone.append(
                generate_phones(phonename, add_text, adb_option,
                                screen, filename, datetimeformat, dummy=False)
            )
        else:
            screen = "/static/dummy.png"
            screens_phone.append(generate_phones(
                phonename, add_text, adb_option, screen, filename, datetimeformat, dummy=True))

    for phonename in adb_connect.return_adb_devices():
        if phonename.serial not in ws_connected_phones:
            for pho in device_mappings:
                if phonename.serial == device_mappings[pho].get('adb', False):
                    adb_option = True
                    add_text = '<b>ADB - no WS<img src="/static/warning.png" width="20px" ' \
                               'alt="NO websocket connection!"></b>'
                    filename = os.path.join(
                        conf_args.temp_path, 'screenshot%s.png' % str(pho))
                    if os.path.isfile(filename):
                        image_resize(filename, os.path.join(
                            conf_args.temp_path, "madmin"), width=200)
                        screen = "/screenshot/madmin/screenshot" + \
                            str(pho) + ".png"
                        screens_phone.append(generate_phones(
                            pho, add_text, adb_option, screen, filename, datetimeformat, dummy=False)
                        )
                    else:
                        screen = "/static/dummy.png"
                        screens_phone.append(
                            generate_phones(pho, add_text, adb_option, screen, filename, datetimeformat,
                                            dummy=True)
                        )

    return render_template('phonescreens.html', editform=screens_phone, header="Phonecontrol", title="Phonecontrol",
                           running_ocr=(conf_args.only_ocr))


@app.route('/screenshot/<path:path>', methods=['GET'])
@auth_required
@nocache
def pushscreens(path):
    return send_from_directory(generate_path(conf_args.temp_path), path)


@app.route('/static/<path:path>', methods=['GET'])
@auth_required
def pushstatic(path):
    return send_from_directory(generate_path('madmin/static'), path)


@app.route('/take_screenshot', methods=['GET'])
@auth_required
def take_screenshot(origin=None, useadb=None):
    global ws_server
    origin = request.args.get('origin')
    useadb = request.args.get('adb', False)
    logger.info('MADmin: Making screenshot ({})', str(origin))
    adb = device_mappings[origin].get('adb', False)

    if useadb == 'True' and adb_connect.make_screenshot(adb, origin):
        logger.info('MADMin: ADB screenshot successfully ({})', str(origin))
    elif conf_args.use_media_projection:
        temp_comm = ws_server.get_origin_communicator(origin)
        temp_comm.getScreenshot(os.path.join(
            conf_args.temp_path, 'screenshot%s.png' % str(origin)))
    else:
        temp_comm = ws_server.get_origin_communicator(origin)
        temp_comm.get_screenshot_single(os.path.join(
            conf_args.temp_path, 'screenshot%s.png' % str(origin)))

    image_resize(os.path.join(conf_args.temp_path, "screenshot" + str(origin) + ".png"),
                 os.path.join(conf_args.temp_path, "madmin"), width=400)

    creationdate = datetime.datetime.fromtimestamp(
        creation_date(os.path.join(conf_args.temp_path, 'screenshot%s.png' % str(origin)))).strftime(datetimeformat)

    return creationdate


@app.route('/click_screenshot', methods=['GET'])
@auth_required
def click_screenshot():
    global ws_server
    origin = request.args.get('origin')
    click_x = request.args.get('clickx')
    click_y = request.args.get('clicky')
    useadb = request.args.get('adb')

    filename = os.path.join(conf_args.temp_path,
                            'screenshot%s.png' % str(origin))
    img = cv2.imread(filename, 0)
    height, width = img.shape[:2]

    real_click_x = int(width / float(click_x))
    real_click_y = int(height / float(click_y))
    adb = device_mappings[origin].get('adb', False)

    if useadb == 'True' and adb_connect.make_screenclick(adb, origin, real_click_x, real_click_y):
        logger.info('MADMin: ADB screenclick successfully ({})', str(origin))
    else:
        logger.info('MADMin WS Click x:{} y:{} ({})', str(
            real_click_x), str(real_click_y), str(origin))
        temp_comm = ws_server.get_origin_communicator(origin)
        temp_comm.click(int(real_click_x), int(real_click_y))

    time.sleep(2)
    return take_screenshot(origin, useadb)


@app.route('/swipe_screenshot', methods=['GET'])
@auth_required
def swipe_screenshot():
    global ws_server
    origin = request.args.get('origin')
    click_x = request.args.get('clickx')
    click_y = request.args.get('clicky')
    click_xe = request.args.get('clickxe')
    click_ye = request.args.get('clickye')
    useadb = request.args.get('adb')

    filename = os.path.join(conf_args.temp_path,
                            'screenshot%s.png' % str(origin))
    img = cv2.imread(filename, 0)
    height, width = img.shape[:2]

    real_click_x = int(width / float(click_x))
    real_click_y = int(height / float(click_y))
    real_click_xe = int(width / float(click_xe))
    real_click_ye = int(height / float(click_ye))
    adb = device_mappings[origin].get('adb', False)

    if useadb == 'True' and adb_connect.make_screenswipe(adb, origin, real_click_x, real_click_y, real_click_xe, real_click_ye):
        logger.info('MADMin: ADB screenswipe successfully ({})', str(origin))
    else:
        logger.info('MADMin WS Swipe x:{} y:{} xe:{} ye:{} ({})', str(real_click_x), str(real_click_y),
                    str(real_click_xe), str(real_click_ye),  str(origin))
        temp_comm = ws_server.get_origin_communicator(origin)
        temp_comm.touchandhold(int(real_click_x), int(
            real_click_y), int(real_click_xe), int(real_click_ye))

    time.sleep(2)
    return take_screenshot(origin, useadb)


@app.route('/quit_pogo', methods=['GET'])
@auth_required
def quit_pogo():
    global ws_server
    origin = request.args.get('origin')
    useadb = request.args.get('adb')
    adb = device_mappings[origin].get('adb', False)
    logger.info('MADmin: Restart Pogo ({})', str(origin))
    if useadb == 'True' and adb_connect.send_shell_command(adb, origin, "am force-stop com.nianticlabs.pokemongo"):
        logger.info('MADMin: ADB shell command successfully ({})', str(origin))
    else:
        temp_comm = ws_server.get_origin_communicator(origin)
        temp_comm.stopApp("com.nianticlabs.pokemongo")
        logger.info('MADMin: WS command successfully ({})', str(origin))

    time.sleep(2)
    return take_screenshot(origin, useadb)


@app.route('/restart_phone', methods=['GET'])
@auth_required
def restart_phone():
    global ws_server
    origin = request.args.get('origin')
    useadb = request.args.get('adb')
    adb = device_mappings[origin].get('adb', False)
    logger.info('MADmin: Restart Phone ({})', str(origin))
    if useadb == 'True' and adb_connect.send_shell_command(adb, origin, "am broadcast -a android.intent.action.BOOT_COMPLETED"):
        logger.info('MADMin: ADB shell command successfully ({})', str(origin))
    else:
        temp_comm = ws_server.get_origin_communicator(origin)
        temp_comm.reboot()
    return redirect(getBasePath(request) + '/phonecontrol')


@app.route('/send_gps', methods=['GET'])
@auth_required
def send_gps():
    global ws_server
    origin = request.args.get('origin')
    useadb = request.args.get('adb')
    coords = request.args.get('coords').replace(' ', '').split(',')
    sleeptime = request.args.get('sleeptime', "0")
    if len(coords) < 2:
        return 'Wrong Format!'
    logger.info('MADmin: Set GPS Coords {}, {} - WS Mode only! ({})',
                str(coords[0]), str(coords[1]), str(origin))
    try:
        temp_comm = ws_server.get_origin_communicator(origin)
        temp_comm.setLocation(coords[0], coords[1], 0)
        if int(sleeptime) > 0:
            logger.info("MADmin: Set additional sleeptime: {} ({})",
                        str(sleeptime), str(origin))
            ws_server.set_geofix_sleeptime_worker(origin, sleeptime)
    except Exception as e:
        logger.exception(
            'MADmin: Exception occurred while set gps coords: {}.', e)

    time.sleep(2)
    return take_screenshot(origin, useadb)


@app.route('/send_text', methods=['GET'])
@auth_required
def send_text():
    global ws_server
    origin = request.args.get('origin')
    useadb = request.args.get('adb')
    text = request.args.get('text')
    adb = device_mappings[origin].get('adb', False)
    if len(text) == 0:
        return 'Empty text'
    logger.info('MADmin: Send text ({})', str(origin))
    if useadb == 'True' and adb_connect.send_shell_command(adb, origin, 'input text "' + text + '"'):
        logger.info('MADMin: Send text successfully ({})', str(origin))
    else:
        temp_comm = ws_server.get_origin_communicator(origin)
        temp_comm.sendText(text)

    time.sleep(2)
    return take_screenshot(origin, useadb)


@app.route('/send_command', methods=['GET'])
@auth_required
def send_command():
    global ws_server
    origin = request.args.get('origin')
    useadb = request.args.get('adb')
    command = request.args.get('command')
    adb = device_mappings[origin].get('adb', False)
    logger.info('MADmin: Sending Command ({})', str(origin))
    if command == 'home':
        cmd = "input keyevent 3"
    elif command == 'back':
        cmd = "input keyevent 4"
    if useadb == 'True' and adb_connect.send_shell_command(adb, origin, cmd):
        logger.info('MADMin: ADB shell command successfully ({})', str(origin))
    else:
        temp_comm = ws_server.get_origin_communicator(origin)
        if command == 'home':
            temp_comm.homeButton()
        elif command == 'back':
            temp_comm.backButton()

    time.sleep(2)
    return take_screenshot(origin, useadb)


@app.route('/screens', methods=['GET'])
@auth_required
def screens():
    return render_template('screens.html', responsive=str(conf_args.madmin_noresponsive).lower(),
                           title="show success Screens", running_ocr=(conf_args.only_ocr))


@app.route('/', methods=['GET'])
@auth_required
def root():
    print(conf_args.only_ocr)
    return render_template('index.html', running_ocr=(conf_args.only_ocr))


@app.route('/raids', methods=['GET'])
@auth_required
def raids():
    return render_template('raids.html', sort=str(conf_args.madmin_sort),
                           responsive=str(conf_args.madmin_noresponsive).lower(),
                           title="show Raid Matching", running_ocr=(conf_args.only_ocr))


@app.route('/gyms', methods=['GET'])
@auth_required
def gyms():
    return render_template('gyms.html', sort=conf_args.madmin_sort,
                           responsive=str(conf_args.madmin_noresponsive).lower(),
                           title="show Gym Matching", running_ocr=(conf_args.only_ocr))


@app.route('/unknown', methods=['GET'])
@auth_required
def unknown():
    return render_template('unknown.html', responsive=str(conf_args.madmin_noresponsive).lower(),
                           title="show unkown Gym", running_ocr=(conf_args.only_ocr))


@app.route('/map', methods=['GET'])
@auth_required
def map():
    return render_template('map.html', lat=conf_args.home_lat, lng=conf_args.home_lng,
                           running_ocr=(conf_args.only_ocr))


@app.route('/quests', methods=['GET'])
def quest():
    return render_template('quests.html', responsive=str(conf_args.madmin_noresponsive).lower(),
                           title="show daily Quests", running_ocr=(conf_args.only_ocr))


@app.route("/submit_hash")
@auth_required
def submit_hash():
    hash = request.args.get('hash')
    id = request.args.get('id')

    if db_wrapper.insert_hash(hash, 'gym', id, '999', unique_hash="madmin"):

        for file in glob.glob("www_hash/unkgym_*" + str(hash) + ".jpg"):
            copyfile(file, 'www_hash/gym_0_0_' + str(hash) + '.jpg')
            os.remove(file)

        return redirect(getBasePath(request) + "/unknown", code=302)


@app.route("/modify_raid_gym")
@auth_required
def modify_raid_gym():
    hash = request.args.get('hash')
    id = request.args.get('id')
    mon = request.args.get('mon')
    lvl = request.args.get('lvl')

    newJsonString = encodeHashJson(id, lvl, mon)
    db_wrapper.delete_hash_table(str(hash), 'raid', 'in', 'hash')
    db_wrapper.insert_hash(hash, 'raid', newJsonString, 
                           '999', unique_hash="madmin")

    return redirect(getBasePath(request) + "/raids", code=302)


@app.route("/modify_raid_mon")
@auth_required
def modify_raid_mon():
    hash = request.args.get('hash')
    id = request.args.get('gym')
    mon = request.args.get('mon')
    lvl = request.args.get('lvl')

    newJsonString = encodeHashJson(id, lvl, mon)
    db_wrapper.delete_hash_table(str(hash), 'raid', 'in', 'hash')
    db_wrapper.insert_hash(hash, 'raid', newJsonString,
                           '999', unique_hash="madmin")

    return redirect(getBasePath(request) + "/raids", code=302)


@app.route("/modify_gym_hash")
@auth_required
def modify_gym_hash():
    hash = request.args.get('hash')
    id = request.args.get('id')

    db_wrapper.delete_hash_table(str(hash), 'gym', 'in', 'hash')
    db_wrapper.insert_hash(hash, 'gym', id, '999', unique_hash="madmin")

    return redirect(getBasePath(request) + "/gyms", code=302)


@app.route("/near_gym")
@auth_required
def near_gym():
    nearGym = []

    data = db_wrapper.get_gym_infos()

    lat = request.args.get('lat')
    lon = request.args.get('lon')
    if lat == "9999":
        distance = int(9999)
        lat = conf_args.home_lat
        lon = conf_args.home_lng
    else:
        distance = int(conf_args.unknown_gym_distance)

    if not lat or not lon:
        return 'Missing Argument...'
    closestGymIds = db_wrapper.get_near_gyms(
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


@app.route("/delete_hash")
@auth_required
def delete_hash():
    hash = request.args.get('hash')
    type = request.args.get('type')
    redi = request.args.get('redirect')
    if not hash or not type:
        return 'Missing Argument...'

    db_wrapper.delete_hash_table(str(hash), type, 'in', 'hash')
    for file in glob.glob("ocr/www_hash/*" + str(hash) + ".jpg"):
        os.remove(file)

    return redirect(getBasePath(request) + '/' + str(redi), code=302)


@app.route("/delete_file")
@auth_required
def delete_file():
    hash = request.args.get('hash')
    type = request.args.get('type')
    redi = request.args.get('redirect')
    if not hash or not type:
        return 'Missing Argument...'

    for file in glob.glob("ocr/www_hash/*" + str(hash) + ".jpg"):
        os.remove(file)

    return redirect(getBasePath(request) + '/' + str(redi), code=302)


@app.route("/get_gyms")
@auth_required
def get_gyms():
    gyms = []
    data = db_wrapper.get_gym_infos()

    hashdata = json.loads(getAllHash('gym'))

    for file in glob.glob("ocr/www_hash/gym_*.jpg"):
        unkfile = re.search(r'gym_(-?\d+)_(-?\d+)_((?s).*)\.jpg', file)
        hashvalue = (unkfile.group(3))

        if str(hashvalue) in hashdata:

            gymid = hashdata[str(hashvalue)]["id"]
            count = hashdata[hashvalue]["count"]
            modify = hashdata[hashvalue]["modify"]

            creationdate = datetime.datetime.fromtimestamp(
                creation_date(file)).strftime(datetimeformat)

            modify = datetime.datetime.strptime(
                modify, '%Y-%m-%d %H:%M:%S').strftime(datetimeformat)

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
            log.debug("File: " + str(file) + " not found in Database")
            os.remove(str(file))
            continue

    return jsonify(gyms)


@app.route("/get_raids")
@auth_required
def get_raids():
    raids = []
    eggIdsByLevel = [1, 1, 2, 2, 3]

    data = db_wrapper.get_gym_infos()

    mondata = open_json_file('pokemon')

    hashdata = json.loads(getAllHash('raid'))

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
                creation_date(file)).strftime(datetimeformat)

            modify = datetime.datetime.strptime(
                modify, '%Y-%m-%d %H:%M:%S').strftime(datetimeformat)

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
                         'count': count, 'creation': creationdate, 'modify': modify,  'level': lvl,
                         'mon': mon, 'type': type, 'eggPic': eggPic, 'monPic': monPic, 'monname': monName})
            raids.append(raidJson)
        else:
            log.debug("File: " + str(file) + " not found in Database")
            os.remove(str(file))
            continue

    return jsonify(raids)


@app.route("/get_mons")
@auth_required
def get_mons():
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


@app.route("/get_screens")
@auth_required
def get_screens():
    screens = []

    for file in glob.glob(str(conf_args.raidscreen_path) + "/raidscreen_*.png"):
        creationdate = datetime.datetime.fromtimestamp(
            creation_date(file)).strftime(datetimeformat)

        screenJson = ({'filename': file[4:], 'creation': creationdate})
        screens.append(screenJson)

    return jsonify(screens)


@app.route("/get_unknowns")
@auth_required
def get_unknowns():
    unk = []
    for file in glob.glob("ocr/www_hash/unkgym_*.jpg"):
        unkfile = re.search(
            r'unkgym_(-?\d+\.?\d+)_(-?\d+\.?\d+)_((?s).*)\.jpg', file)
        creationdate = datetime.datetime.fromtimestamp(
            creation_date(file)).strftime(datetimeformat)
        lat = (unkfile.group(1))
        lon = (unkfile.group(2))
        hashvalue = (unkfile.group(3))

        hashJson = ({'lat': lat, 'lon': lon, 'hashvalue': hashvalue,
                     'filename': file[4:], 'creation': creationdate})
        unk.append(hashJson)

    return jsonify(unk)


@app.route("/get_position")
@auth_required
def get_position():
    positions = []

    for name, device in device_mappings.items():
        try:
            with open(os.path.join(conf_args.file_path, name + '.position'), 'r') as f:
                latlon = f.read().strip().split(', ')
                worker = {
                    'name': str(name),
                    'lat': getCoordFloat(latlon[0]),
                    'lon': getCoordFloat(latlon[1])
                }
                positions.append(worker)
        except OSError:
            pass

    return jsonify(positions)


@cache.cached()
@app.route("/get_geofence")
@auth_required
def get_geofence():
    geofences = {}

    for name, area in areas.items():
        geofence_include = {}
        geofence_exclude = {}
        geofence_name = 'Unknown'
        geofence_included = Path(area["geofence_included"])
        if not geofence_included.is_file():
            continue
        with geofence_included.open() as gf:
            for line in gf:
                line = line.strip()
                if not line:  # Empty line.
                    continue
                elif line.startswith("["):  # Name line.
                    geofence_name = line.replace("[", "").replace("]", "")
                    geofence_include[geofence_name] = []
                else:  # Coordinate line.
                    lat, lon = line.split(",")
                    geofence_include[geofence_name].append([
                        getCoordFloat(lon),
                        getCoordFloat(lat)
                    ])

        if area['geofence_excluded']:
            geofence_name = 'Unknown'
            geofence_excluded = Path(area["geofence_excluded"])
            if not geofence_excluded.is_file():
                continue
            with geofence_excluded.open() as gf:
                for line in gf:
                    line = line.strip()
                    if not line:  # Empty line.
                        continue
                    elif line.startswith("["):  # Name line.
                        geofence_name = line.replace("[", "").replace("]", "")
                        geofence_exclude[geofence_name] = []
                    else:  # Coordinate line.
                        lat, lon = line.split(",")
                        geofence_exclude[geofence_name].append([
                            getCoordFloat(lon),
                            getCoordFloat(lat)
                        ])

        geofences[name] = {'include': geofence_include,
                           'exclude': geofence_exclude}

    geofencexport = []
    for name, fences in geofences.items():
        coordinates = []
        for fname, coords in fences.get('include').items():
            coordinates.append([coords, fences.get('exclude').get(fname, [])])
        geofencexport.append({'name': name, 'coordinates': coordinates})

    return jsonify(geofencexport)


@cache.cached()
@app.route("/get_route")
@auth_required
def get_route():
    routeexport = []

    for name, area in areas.items():
        route = []
        try:
            with open(os.path.join(conf_args.file_path, area['routecalc'] + '.calc'), 'r') as f:
                for line in f.readlines():
                    latlon = line.strip().split(', ')
                    route.append([
                        getCoordFloat(latlon[0]),
                        getCoordFloat(latlon[1])
                    ])
                routeexport.append(
                    {'name': str(name), 'mode': area['mode'], 'coordinates': route})
        # ignore missing routes files
        except OSError:
            pass

    return jsonify(routeexport)


@app.route("/get_spawns")
@auth_required
def get_spawns():
    coords = []
    data = json.loads(db_wrapper.download_spawns())

    for spawnid in data:
        spawn = data[str(spawnid)]
        coords.append({
            'endtime': spawn['endtime'],
            'lat': spawn['lat'],
            'lon': spawn['lon'],
            'spawndef': spawn['spawndef'],
            'lastscan': spawn['lastscan']
        })

    return jsonify(coords)


@cache.cached()
@app.route("/get_gymcoords")
@auth_required
def get_gymcoords():
    coords = []

    data = db_wrapper.get_gym_infos()

    for gymid in data:
        gym = data[str(gymid)]
        coords.append({
            'id': gymid,
            'name': gym['name'],
            'img': gym['url'],
            'lat': gym['latitude'],
            'lon': gym['longitude'],
            'team_id': gym['team_id']
        })

    return jsonify(coords)


@app.route("/get_quests")
@auth_required
def get_quests():
    coords = []

    data = db_wrapper.quests_from_db()

    for pokestopid in data:
        quest = data[str(pokestopid)]
        coords.append(generate_quest(quest))

    return jsonify(coords)


@app.route('/gym_img/<path:path>', methods=['GET'])
@auth_required
def pushGyms(path):
    return send_from_directory('../ocr/gym_img', path)


@app.route('/www_hash/<path:path>', methods=['GET'])
@auth_required
def pushHashes(path):
    return send_from_directory('../ocr/www_hash', path)


@app.route('/screenshots/<path:path>', methods=['GET'])
@auth_required
def pushScreens(path):
    return send_from_directory('../' + conf_args.raidscreen_path, path)


@app.route('/match_unknowns', methods=['GET'])
@auth_required
def match_unknowns():
    hash = request.args.get('hash')
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    return render_template('match_unknown.html', hash=hash, lat=lat, lon=lon, responsive=str(conf_args.madmin_noresponsive).lower(), title="match Unknown", running_ocr=(conf_args.only_ocr))


@app.route('/modify_raid', methods=['GET'])
@auth_required
def modify_raid():
    hash = request.args.get('hash')
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    lvl = request.args.get('lvl')
    mon = request.args.get('mon')
    return render_template('change_raid.html', hash=hash, lat=lat, lon=lon, lvl=lvl, mon=mon, responsive=str(conf_args.madmin_noresponsive).lower(), title="change Raid", running_ocr=(conf_args.only_ocr))


@app.route('/modify_gym', methods=['GET'])
@auth_required
def modify_gym():
    hash = request.args.get('hash')
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    return render_template('change_gym.html', hash=hash, lat=lat, lon=lon, responsive=str(conf_args.madmin_noresponsive).lower(), title="change Gym", running_ocr=(conf_args.only_ocr))


@app.route('/modify_mon', methods=['GET'])
@auth_required
def modify_mon():
    hash = request.args.get('hash')
    gym = request.args.get('gym')
    lvl = request.args.get('lvl')
    return render_template('change_mon.html', hash=hash, gym=gym, lvl=lvl, responsive=str(conf_args.madmin_noresponsive).lower(), title="change Mon", running_ocr=(conf_args.only_ocr))


@app.route('/asset/<path:path>', methods=['GET'])
@auth_required
def pushAssets(path):
    return send_from_directory(conf_args.pogoasset, path)


@app.route('/addwalker')
@auth_required
def addwalker():
    fieldwebsite = []
    walkervalue = ""
    walkerposition = ""
    walkermax = ""
    walkertext = ""
    edit = request.args.get('edit')
    walker = request.args.get('walker')
    add = request.args.get('add')

    walkernr = request.args.get('walkernr')

    with open('configs/mappings.json') as f:
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

        with open('configs/mappings.json', 'w') as outfile:
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
    with open('configs/mappings.json') as f:
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
                        '<input type="text" name="walkervalue" value="' + str(walkervalue) + '"></div>')

    fieldwebsite.append('<div class="form-group"><label>Max. Walker in Area</label><br />'
                        '<small class="form-text text-muted">Empty = infinitely</small>'
                        '<input type="text" name="walkermax" value="' + str(walkermax) + '"></div>')

    fieldwebsite.append('<div class="form-group"><label>Description</label><br />'
                        '<small class="form-text text-muted"></small>'
                        '<input type="text" name="walkertext" value="' + str(walkertext).replace('_', ' ') + '"></div>')

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
                           running_ocr=(conf_args.only_ocr))


@app.route('/savesortwalker', methods=['GET', 'POST'])
@auth_required
def savesortwalker():
    walkernr = request.args.get('walkernr')
    data = request.args.getlist('position[]')
    edit = request.args.get('edit')
    datavalue = []

    with open('configs/mappings.json') as f:
        mapping = json.load(f)
        if 'walker' not in mapping:
            mapping['walker'] = []

    for ase in data:
        _temp = ase.split("|")
        walkerlist = {'walkerarea': _temp[0], 'walkertype': _temp[1], 'walkervalue': _temp[2], 'walkermax': _temp[3],
                      'walkertext': _temp[4]}
        datavalue.append(walkerlist)

    mapping['walker'][int(walkernr)]['setup'] = datavalue

    with open('configs/mappings.json', 'w') as outfile:
        json.dump(mapping, outfile, indent=4, sort_keys=True)

    return redirect(getBasePath(request) + "/config?type=walker&area=walker&block=fields&edit=" + str(edit), code=302)


@app.route('/delwalker')
@auth_required
def delwalker():
    walker = request.args.get('walker')
    walkernr = request.args.get('walkernr')
    walkerposition = request.args.get('walkerposition')

    with open('configs/mappings.json') as f:
        mapping = json.load(f)
        if 'walker' not in mapping:
            mapping['walker'] = []

    del mapping['walker'][int(walkernr)]['setup'][int(walkerposition)]

    with open('configs/mappings.json', 'w') as outfile:
        json.dump(mapping, outfile, indent=4, sort_keys=True)

    return redirect(getBasePath(request) + "/config?type=walker&area=walker&block=fields&edit=" + str(walker), code=302)


@app.route('/config')
@auth_required
def config():
    fieldwebsite = []
    oldvalues = []
    sel = ''
    _walkernr = 0

    edit = False
    edit = request.args.get('edit')
    type = request.args.get('type')
    block = request.args.get('block')
    area = request.args.get('area')
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
        with open('configs/mappings.json') as f:
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

    for field in compfields[block]:
        lock = field['settings'].get("lockonedit", False)
        lockvalue = 'readonly' if lock and edit else ''
        req = 'required' if field['settings'].get(
            'require', 'false') == 'true' else ''
        if field['settings']['type'] == 'text' or field['settings']['type'] == 'textarea':
            val = ''
            if edit:
                if block == 'settings':
                    if field['name'] in oldvalues['settings'] and str(oldvalues['settings'][field['name']]) != str('None'):
                        val = str(oldvalues['settings'][field['name']])
                else:
                    if field['name'] in oldvalues and str(oldvalues[field['name']]) != str('None'):
                        val = str(oldvalues[field['name']])

            formStr = '<div class="form-group">'
            formStr += '<label>' + str(field['name']) + '</label><br /><small class="form-text text-muted">' + str(
                field['settings']['description']) + '</small>'
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
                                val[i]['walkertype']) + '|' + str(val[i]['walkervalue']) + '|' + str(val[i].get('walkermax', '')) + '|' + str(val[i].get('walkertext', '')).replace(' ', '_') + '>'
                                '<td ><img src="static/sort.png" class="handle"></td><td>' + str(i) + '</td><td><b>' + str(val[i]['walkerarea']) + '</b><br>' + str(val[i].get('walkertext', '')).replace('_', ' ') + '</td><td>' + str(
                                val[i]['walkertype']) + '</td><td>' + str(val[i]['walkervalue']) + '</td><td>' + str(val[i].get('walkermax', '')) + '</td><td>'
                                '<a href="delwalker?walker=' + str(edit) + '&walkernr=' + str(
                                    _walkernr) + '&walkerposition=' + str(i) + '">Delete</a><br>'
                                '<a href="addwalker?walker=' + str(edit) + '&walkernr=' + str(_walkernr) + '&walkerposition=' + str(i) + '&edit=True">Edit</a></form></td></tr>')
                            i += 1

                    fieldwebsite.append('</tbody></table>')
                    fieldwebsite.append(
                        '<div class="form-group"><a href="addwalker?walker=' + str(edit) + '&walkernr=' + str(
                            _walkernr) + '">Add Area</a></div>')

        if field['settings']['type'] == 'option':
            _temp = '<div class="form-group"><label>' + str(field['name']) + '</label><br /><small class="form-text text-muted">' + str(
                field['settings']['description']) + '</small><select class="form-control" name="' + str(field['name']) + '" ' + lockvalue + ' ' + req + '>'
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
            _temp = '<div class="form-group"><label>' + str(field['name']) + '</label><br /><small class="form-text text-muted">' + str(
                field['settings']['description']) + '</small><select class="form-control" name="' + str(field['name']) + '" ' + lockvalue + ' ' + req + '>'
            with open('configs/mappings.json') as f:
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
            devices = adb_connect.return_adb_devices()
            _temp = '<div class="form-group"><label>' + str(field['name']) + '</label><br /><small class="form-text text-muted">' + str(
                field['settings']['description']) + '</small><select class="form-control" name="' + str(field['name']) + '" ' + lockvalue + ' ' + req + '>'
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
            _temp = '<div class="form-group"><label>' + str(field['name']) + '</label><br /><small class="form-text text-muted">' + str(
                field['settings']['description']) + '</small><select class="form-control" name="' + str(field['name']) + '" ' + lockvalue + ' ' + req + '>'
            with open('configs/mappings.json') as f:
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

        if field['settings']['type'] == 'poolselect':
            _temp = '<div class="form-group"><label>' + str(field['name']) + '</label><br /><small class="form-text text-muted">' + str(
                field['settings']['description']) + '</small><select class="form-control" name="' + str(field['name']) + '" ' + lockvalue + ' ' + req + '>'
            with open('configs/mappings.json') as f:
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
            _temp = '<div class="form-group"><label>' + str(field['name']) + '</label><br /><small class="form-text text-muted">' + str(
                field['settings']['description']) + '</small><select class="form-control" name="' + str(field['name']) + '" ' + lockvalue + ' ' + req + ' size=10 multiple=multiple>'
            with open('configs/mappings.json') as f:
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
                    print(oldvalues[field['name']])
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
                           walkernr=_walkernr, edit=edit, running_ocr=(conf_args.only_ocr))


@app.route('/delsetting', methods=['GET'])
@auth_required
def delsetting():
    global device_mappings, areas
    edit = request.args.get('edit')
    area = request.args.get('area')

    with open('configs/mappings.json') as f:
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

        if str(edit) in str(entry[_checkfield]):
            del mapping[area][key]

    with open('configs/mappings.json', 'w') as outfile:
        json.dump(mapping, outfile, indent=4, sort_keys=True)

    mapping_parser = MappingParser(db_wrapper, conf_args)
    device_mappings = mapping_parser.get_devicemappings()
    areas = mapping_parser.get_areas()

    return redirect(getBasePath(request) + "/showsettings", code=302)


def check_float(number):
    try:
        float(number)
        return True
    except ValueError:
        return False


@app.route('/addedit', methods=['POST'])
@auth_required
def addedit():
    global device_mappings, areas
    data = request.form.to_dict(flat=False)
    datavalue = {}

    for ase in data:
        key = ','.join(data[ase])
        datavalue[ase] = key

    edit = datavalue.get("edit", False)
    block = datavalue.get("block", False)
    area = datavalue.get("area", False)
    mode = datavalue.get("mode", False)

    try:

        with open('configs/mappings.json') as f:
            mapping = json.load(f)
            if 'walker' not in mapping:
                mapping['walker'] = []
            if 'devicesettings' not in mapping:
                mapping['devicesettings'] = []

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
                                    entry['settings'][key] = match_type(value)

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
                                    entry[key] = match_type(value)

        else:
            new = {}
            for key, value in datavalue.items():
                if value != '' and value not in area:
                    if str(key) in ('geofence'):
                        new[key] = value
                    elif str(key) not in ('block', 'area', 'type', 'edit'):
                        new[key] = match_type(value)

            if str(block) == str("settings"):
                mapping[area]['settings'].append(new)
            else:
                if settings[area]['has_settings'] == 'true':
                    new['settings'] = {}
                mapping[area].append(new)

        with open('configs/mappings.json', 'w') as outfile:
            json.dump(mapping, outfile, indent=4, sort_keys=True)

        mapping_parser = MappingParser(db_wrapper, conf_args)
        device_mappings = mapping_parser.get_devicemappings()
        areas = mapping_parser.get_areas()

    except:
        log.info('Invalid data')
        return redirect(getBasePath(request) + '/config?type='+mode+'&area='+area+'&block='+block+'&edit='+edit, code=302)

    return redirect(getBasePath(request) + "/showsettings", code=302)


def match_type(value):
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
    elif check_float(value):
        value = float(value)
    elif value == "None":
        value = None
    else:
        value = value.replace(' ', '_')
    return value


@app.route('/showsettings')
@auth_required
def showsettings():
    table = ''
    with open('configs/mappings.json') as f:
        mapping = json.load(f)
        if 'walker' not in mapping:
            mapping['walker'] = []
        if 'devicesettings' not in mapping:
            mapping['devicesettings'] = []

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

        for output in mapping[var]:
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
                _typearea) + '&block=settings&edit=' + str(output[_field]) + '&del=true">[Delete]</a></td>'

            line = line + '<tr><td><b>' + \
                str(output[_field]) + '</b></td>' + str(edit) + \
                str(editsettings) + str(delete) + '</tr>'

            if _quick == 'setup':
                quickadd = 'Assigned areas: ' + \
                    str(len(output.get('setup', []))) + '<br />Areas: '
                for area in output.get('setup', []):
                    quickadd = quickadd + area.get('walkerarea') + ' | '

                quickline = quickline + '<tr><td></td><td colspan="3" class="quick">' + \
                    str(quickadd) + ' </td><td style="display: none;"></td><td style="display: none;"></td><td style="display: none;"></td>'

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

        table = table + header + subheader + line

    return render_template('settings.html', settings='<table>' + globalheader + '<tbody>' + table + '</tbody></table>',
                           title="Mapping Editor", responsive=str(conf_args.madmin_noresponsive).lower(),
                           running_ocr=(conf_args.only_ocr))


@app.route('/addnew', methods=['GET'])
@auth_required
def addnew():
    area = request.args.get('area')
    line = ''
    with open('madmin/static/vars/vars_parser.json') as f:
        settings = json.load(f)
    if (len(settings[area])) == 1:
        return redirect(getBasePath(request) + '/config?type=' + area + '&area=' + area + '&block=fields', code=302)

    for output in settings[area]:
        line = line + '<h3><a href="config?type=' + str(output['name']) + '&area=' + str(
            area) + '&block=fields">'+str(output['name'])+'</a></h3><h5>'+str(output['description'])+'</h5><hr>'

    return render_template('sel_type.html', line=line, title="Type selector", running_ocr=(conf_args.only_ocr))


@app.route('/status', methods=['GET'])
@auth_required
def status():
    return render_template('status.html', responsive=str(conf_args.madmin_noresponsive).lower(), title="Worker status",
                           running_ocr=(conf_args.only_ocr))


@app.route('/statistics', methods=['GET'])
@auth_required
def statistics():
    minutes_usage = request.args.get('minutes_usage')
    if not minutes_usage:
        minutes_usage = 120
    minutes_spawn = request.args.get('minutes_spawn')
    if not minutes_spawn:
        minutes_spawn = 120

    return render_template('statistics.html', title="MAD Statisics", minutes_spawn=minutes_spawn,
                           minutes_usage=minutes_usage, time=conf_args.madmin_time, running_ocr=(conf_args.only_ocr))


@app.route('/get_status', methods=['GET'])
@auth_required
def get_status():
    data = json.loads(db_wrapper.download_status())
    return jsonify(data)


@app.route('/get_game_stats', methods=['GET'])
@auth_required
def game_stats():
    minutes_usage = request.args.get('minutes_usage')
    minutes_spawn = request.args.get('minutes_spawn')
    # Stop
    stop = []
    data = db_wrapper.statistics_get_stop_quest()
    for dat in data:
        stop.append({'label': dat[0], 'data': dat[1]})

    # Quest
    quest = db_wrapper.statistics_get_quests_count(1)

    # Usage
    insta = {}
    usage = []
    idx = 0
    usa = db_wrapper.statistics_get_usage_count(minutes_usage)

    for dat in usa:
        if 'CPU-' + dat[4] not in insta:
            insta['CPU-' + dat[4]] = {}
            insta['CPU-' + dat[4]]["axis"] = 1
            insta['CPU-' + dat[4]]["data"] = []
        if 'MEM-' + dat[4] not in insta:
            insta['MEM-' + dat[4]] = {}
            insta['MEM-' + dat[4]]['axis'] = 2
            insta['MEM-' + dat[4]]["data"] = []
        if conf_args.stat_gc:
            if 'CO-' + dat[4] not in insta:
                insta['CO-' + dat[4]] = {}
                insta['CO-' + dat[4]]['axis'] = 3
                insta['CO-' + dat[4]]["data"] = []

        insta['CPU-' + dat[4]]['data'].append([dat[3] * 1000, dat[0]])
        insta['MEM-' + dat[4]]['data'].append([dat[3] * 1000, dat[1]])
        if conf_args.stat_gc:
            insta['CO-' + dat[4]]['data'].append([dat[3] * 1000, dat[2]])

    for label in insta:
        usage.append(
            {'label': label, 'data': insta[label]['data'], 'yaxis': insta[label]['axis'], 'idx': idx})
        idx += 1

    # Gym
    gym = []
    data = db_wrapper.statistics_get_gym_count()
    for dat in data:
        if dat[0] == 'WHITE':
            color = '#999999'
            text = 'Uncontested'
        elif dat[0] == 'BLUE':
            color = '#0051CF'
            text = 'Mystic'
        elif dat[0] == 'RED':
            color = '#FF260E'
            text = 'Valor'
        elif dat[0] == 'YELLOW':
            color = '#FECC23'
            text = 'Instinct'
        gym.append({'label': text, 'data': dat[1], 'color': color})

    # Spawn
    iv = []
    noniv = []
    sum = []
    sumup = {}

    data = db_wrapper.statistics_get_pokemon_count(minutes_spawn)
    for dat in data:
        if dat[2] == 1:
            iv.append([(dat[0]*1000), dat[1]])
        else:
            noniv.append([(dat[0]*1000), dat[1]])

        if (dat[0]*1000) in sumup:
            sumup[(dat[0]*1000)] += dat[1]
        else:
            sumup[(dat[0]*1000)] = dat[1]

    for dat in sumup:
        sum.append([dat, sumup[dat]])

    spawn = {'iv': iv, 'noniv': noniv, 'sum': sum}

    stats = {'spawn': spawn, 'gym': gym,
             'quest': quest, 'stop': stop, 'usage': usage}
    return jsonify(stats)


def getBasePath(request):
    if request.referrer:
        return '/'.join(request.referrer.split('/')[:-1])
    return ''


def decodeHashJson(hashJson):
    data = json.loads(hashJson)
    raidGym = data['gym']
    raidLvl = data["lvl"]
    raidMon = data["mon"]

    return raidGym, raidLvl, raidMon


def encodeHashJson(gym, lvl, mon):
    hashJson = json.dumps(
        {'gym': gym, 'lvl': lvl, 'mon': mon}, separators=(',', ':'))
    return hashJson


def getAllHash(type):
    rv = db_wrapper.get_all_hash(type)
    hashRes = {}
    for result in rv:
        hashRes[result[1]] = ({'id': str(
            result[0]), 'type': result[2], 'count': result[3], 'modify': str(result[4])})
    return json.dumps(hashRes, indent=4, sort_keys=True)


def getCoordFloat(coordinate):
    return floor(float(coordinate) * (10 ** 5)) / float(10 ** 5)
