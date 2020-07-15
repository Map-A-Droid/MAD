import datetime
import glob
import os
from functools import update_wrapper, wraps
from math import floor

from flask import (make_response, request)

from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.utils.functions import creation_date
from mapadroid.utils.walkerArgs import parse_args

mapping_args = parse_args()


def auth_required(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        username = getattr(mapping_args, 'madmin_user', '')
        password = getattr(mapping_args, 'madmin_password', '')
        quests_pub_enabled = getattr(mapping_args, 'quests_public', False)

        if not username:
            return func(*args, **kwargs)
        if quests_pub_enabled and func.__name__ in ['get_quests', 'quest_pub', 'pushassets']:
            return func(*args, **kwargs)
        if request.authorization:
            if (request.authorization.username == username) and (
                    request.authorization.password == password):
                return func(*args, **kwargs)
        return make_response('Could not verify!', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})

    return decorated


def allowed_file(filename):
    allowed_extensions = set(['apk', 'txt'])
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


def uploaded_files(datetimeformat, jobs):
    files = []
    for apk_file in glob.glob(str(mapping_args.upload_path) + "/*.apk"):
        creationdate = datetime.datetime.fromtimestamp(
            creation_date(apk_file)).strftime(datetimeformat)
        upfile = {
            'jobname': os.path.basename(apk_file),
            'creation': creationdate,
            'type': 'jobType.INSTALLATION'
        }
        files.append((upfile))

    for command in jobs:
        files.append({'jobname': command, 'creation': '', 'type': 'jobType.CHAIN'})

    return files


def nocache(view):
    @wraps(view)
    def no_cache(*args, **kwargs):
        response = make_response(view(*args, **kwargs))
        response.headers['Last-Modified'] = datetime.datetime.now()
        response.headers[
            'Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
        return response

    return update_wrapper(no_cache, view)


def get_bound_params(request):
    ne_lat = request.args.get('neLat')
    ne_lon = request.args.get('neLon')
    sw_lat = request.args.get('swLat')
    sw_lon = request.args.get('swLon')
    o_ne_lat = request.args.get('oNeLat', None)
    o_ne_lon = request.args.get('oNeLon', None)
    o_sw_lat = request.args.get('oSwLat', None)
    o_sw_lon = request.args.get('oSwLon', None)

    # reset old bounds to None if they're equal
    # this will tell the query to only fetch new/updated elements
    if ne_lat == o_ne_lat and ne_lon == o_ne_lon and sw_lat == o_sw_lat and sw_lon == o_sw_lon:
        o_ne_lat = o_ne_lon = o_sw_lat = o_sw_lon = None

    return ne_lat, ne_lon, sw_lat, sw_lon, o_ne_lat, o_ne_lon, o_sw_lat, o_sw_lon


def get_coord_float(coordinate):
    return floor(float(coordinate) * (10 ** 5)) / float(10 ** 5)


def generate_device_screenshot_path(phone_name: str, device_mappings: dict, args: dict):
    screenshot_ending: str = ".jpg"
    if device_mappings[phone_name].get("screenshot_type", "jpeg") == "png":
        screenshot_ending = ".png"
    screenshot_filename = "screenshot_{}{}".format(phone_name, screenshot_ending)
    return os.path.join(args.temp_path, screenshot_filename)


def generate_device_logcat_zip_path(origin: str, args: dict):
    filename = "logcat_{}.zip".format(origin)
    return os.path.join(args.temp_path, filename)


def get_geofences(mapping_manager, data_manager, fence_type=None, area_id_req=None):
    areas = mapping_manager.get_areas()
    geofences = {}
    for area_id, area in areas.items():
        if area_id_req is not None and int(area_id) is not int(area_id_req):
            continue
        geo_include = data_manager.get_resource('geofence', identifier=area["geofence_included"])
        geo_exclude_id = area.get("geofence_excluded", None)
        geo_exclude = None
        if geo_exclude_id is not None:
            geo_exclude = data_manager.get_resource('geofence', identifier=geo_exclude_id)
        if fence_type is not None and area['mode'] != fence_type:
            continue
        area_geofences = GeofenceHelper(geo_include, geo_exclude, area['name'])
        include = {}
        exclude = {}
        for fences in area_geofences.geofenced_areas:
            include[fences['name']] = []
            for fence in fences['polygon']:
                include[fences['name']].append([get_coord_float(fence['lat']), get_coord_float(fence['lon'])])
        for fences in area_geofences.excluded_areas:
            exclude[fences['name']] = []
            for fence in fences['polygon']:
                exclude[fences['name']].append([get_coord_float(fence['lat']), get_coord_float(fence['lon'])])
        geofences[area_id] = {
            'include': include,
            'exclude': exclude,
            'mode': area['mode'],
            'area_id': area_id,
            'name': area['name']
        }
    return geofences


def generate_coords_from_geofence(mapping_manager, data_manager, fence):
    fence_string = []
    geofences = get_geofences(mapping_manager, data_manager)
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


def get_quest_areas(mapping_manager, data_manager):
    stop_fences = []
    stop_fences.append('All')
    possible_fences = get_geofences(mapping_manager, data_manager, 'pokestops')
    for possible_fence in get_geofences(mapping_manager, data_manager, 'pokestops'):
        for subfence in possible_fences[possible_fence]['include']:
            if subfence in stop_fences:
                continue
            stop_fences.append(subfence)

    return stop_fences
