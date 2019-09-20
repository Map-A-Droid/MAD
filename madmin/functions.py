import json
import datetime
import os
import glob
from flask import (make_response, request)
from functools import update_wrapper, wraps
from math import floor
from utils.walkerArgs import parseArgs
from utils.functions import (creation_date)
from pathlib import Path

mapping_args = parseArgs()

def auth_required(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        username = getattr(mapping_args, 'madmin_user', '')
        password = getattr(mapping_args, 'madmin_password', '')
        quests_pub_enabled = getattr(mapping_args, 'quests_public', False)

        if not username:
            return func(*args, **kwargs)
        if quests_pub_enabled and func.__name__ in ['get_quests', 'quest_pub', 'pushAssets']:
            return func(*args, **kwargs)
        if request.authorization:
            if (request.authorization.username == username) and (
                    request.authorization.password == password):
                return func(*args, **kwargs)
        return make_response('Could not verify!', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})

    return decorated


def allowed_file(filename):
    ALLOWED_EXTENSIONS = set(['apk', 'txt'])
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def uploaded_files(datetimeformat, jobs):
    files = []
    for file in glob.glob(str(mapping_args.upload_path) + "/*.apk"):
        creationdate = datetime.datetime.fromtimestamp(
            creation_date(file)).strftime(datetimeformat)
        fileJson = ({'jobname': os.path.basename(file), 'creation': creationdate, 'type': 'jobType.INSTALLATION'})
        files.append(fileJson)

    for command in jobs:
        files.append({'jobname': command, 'creation': '', 'type': 'jobType.CHAIN'})

    processJson = ({'jobname': 'Reboot-Phone', 'creation': '', 'type': 'jobType.REBOOT'})
    files.append(processJson)
    processJson = ({'jobname': 'Restart-Pogo', 'creation': '', 'type': 'jobType.RESTART'})
    files.append(processJson)
    processJson = ({'jobname': 'Stop-Pogo', 'creation': '', 'type': 'jobType.STOP'})
    files.append(processJson)
    processJson = ({'jobname': 'Start-Pogo', 'creation': '', 'type': 'jobType.START'})
    files.append(processJson)
    return files


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


def getBoundParameter(request):
    neLat = request.args.get('neLat')
    neLon = request.args.get('neLon')
    swLat = request.args.get('swLat')
    swLon = request.args.get('swLon')
    oNeLat = request.args.get('oNeLat', None)
    oNeLon = request.args.get('oNeLon', None)
    oSwLat = request.args.get('oSwLat', None)
    oSwLon = request.args.get('oSwLon', None)

    # reset old bounds to None if they're equal
    # this will tell the query to only fetch new/updated elements
    if neLat == oNeLat and neLon == oNeLon and swLat == oSwLat and swLon == oSwLon:
        oNeLat = oNeLon = oSwLat = oSwLon = None

    return neLat, neLon, swLat, swLon, oNeLat, oNeLon, oSwLat, oSwLon


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


def getCoordFloat(coordinate):
    return floor(float(coordinate) * (10 ** 5)) / float(10 ** 5)


def generate_device_screenshot_path(phone_name: str, device_mappings: dict, args: dict):
    screenshot_ending: str = ".jpg"
    if device_mappings[phone_name].get("screenshot_type", "jpeg") == "png":
        screenshot_ending = ".png"
    screenshot_filename = "screenshot_{}{}".format(phone_name, screenshot_ending)
    return os.path.join(args.temp_path, screenshot_filename)


def get_geofences(mapping_manager, fence_type=None):
    areas = mapping_manager.get_areas()
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
                        getCoordFloat(lat),
                        getCoordFloat(lon)
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
                            getCoordFloat(lat),
                            getCoordFloat(lon)
                        ])

        if fence_type is not None and area['mode'] != fence_type:
            continue

        geofences[name] = {'include': geofence_include,
                           'exclude': geofence_exclude}

    return geofences


def generate_coords_from_geofence(mapping_manager, fence):
    fence_string = []
    geofences = get_geofences(mapping_manager)
    coordinates = []
    for name, fences in geofences.items():
        for fname, coords in fences.get('include').items():
            if fname != fence:
                continue
            coordinates.append(coords)

    for coord in coordinates[0]:
        fence_string.append(str(coord[0]) + " " + str(coord[1]))

    fence_string.append(fence_string[0])
    return ",".join(fence_string)


def get_quest_areas(mapping_manager):
    stop_fences = []
    stop_fences.append('All')
    possible_fences = get_geofences(mapping_manager, 'pokestops')
    for possible_fence in get_geofences(mapping_manager, 'pokestops'):
        for subfence in possible_fences[possible_fence]['include']:
            if subfence in stop_fences:
                continue
            stop_fences.append(subfence)

    return stop_fences
