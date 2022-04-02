import glob
import os
from functools import update_wrapper, wraps
from math import floor
from typing import Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.mapping_manager.MappingManager import (AreaEntry, DeviceMappingsEntry,
                                                      MappingManager)
from mapadroid.utils.DatetimeWrapper import DatetimeWrapper
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
    allowed_extensions = {'apk', 'txt'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


def uploaded_files(datetimeformat, jobs):
    files = []
    for apk_file in glob.glob(str(mapping_args.upload_path) + "/*.apk"):
        creationdate = DatetimeWrapper.fromtimestamp(
            creation_date(apk_file)).strftime(datetimeformat)
        upfile = {
            'jobname': os.path.basename(apk_file),
            'creation': creationdate,
            'type': 'JobType.INSTALLATION'
        }
        files.append((upfile))

    for command in jobs:
        files.append({'jobname': command, 'creation': '', 'type': 'JobType.CHAIN'})

    return files


def nocache(view):
    @wraps(view)
    def no_cache(*args, **kwargs):
        response = make_response(view(*args, **kwargs))
        response.headers['Last-Modified'] = DatetimeWrapper.now()
        response.headers[
            'Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
        return response

    return update_wrapper(no_cache, view)


def get_bound_params(request):
    try:
        ne_lat = float(request.query.get('neLat'))
    except (ValueError, TypeError):
        ne_lat = None
    try:
        ne_lon = float(request.query.get('neLon'))
    except (ValueError, TypeError):
        ne_lon = None
    try:
        sw_lat = float(request.query.get('swLat'))
    except (ValueError, TypeError):
        sw_lat = None
    try:
        sw_lon = float(request.query.get('swLon'))
    except (ValueError, TypeError):
        sw_lon = None
    try:
        o_ne_lat = float(request.query.get('oNeLat'))
    except (ValueError, TypeError):
        o_ne_lat = None
    try:
        o_ne_lon = float(request.query.get('oNeLon'))
    except (ValueError, TypeError):
        o_ne_lon = None
    try:
        o_sw_lat = float(request.query.get('oSwLat'))
    except (ValueError, TypeError):
        o_sw_lat = None
    try:
        o_sw_lon = float(request.query.get('oSwLon'))
    except (ValueError, TypeError):
        o_sw_lon = None

    # reset old bounds to None if they're equal
    # this will tell the query to only fetch new/updated elements
    if ne_lat == o_ne_lat and ne_lon == o_ne_lon and sw_lat == o_sw_lat and sw_lon == o_sw_lon:
        o_ne_lat = o_ne_lon = o_sw_lat = o_sw_lon = None

    return ne_lat, ne_lon, sw_lat, sw_lon, o_ne_lat, o_ne_lon, o_sw_lat, o_sw_lon


def get_coord_float(coordinate):
    return floor(float(coordinate) * (10 ** 5)) / float(10 ** 5)


def generate_device_screenshot_path(phone_name: str, device_mappings: DeviceMappingsEntry, args):
    screenshot_ending: str = ".jpg"
    if device_mappings.device_settings.screenshot_type == "png":
        screenshot_ending = ".png"
    screenshot_filename = "screenshot_{}{}".format(phone_name, screenshot_ending)
    return os.path.join(args.temp_path, screenshot_filename)


def generate_device_logcat_zip_path(origin: str, args):
    filename = "logcat_{}.zip".format(origin)
    return os.path.join(args.temp_path, filename)


async def get_geofences(mapping_manager: MappingManager, session: AsyncSession, instance_id: int,
                        fence_type=None, area_id_req=None) -> Dict[int, Dict]:
    # TODO: Request the geofence instances from the MappingManager directly?
    areas: Dict[int, AreaEntry] = await mapping_manager.get_areas()
    geofences = {}
    for area_id, area_entry in areas.items():
        if area_id_req is not None and int(area_id) is not int(area_id_req):
            continue
        # geofence_included: Optional[SettingsGeofence] = await SettingsGeofenceHelper.get(session, instance_id,
        #                                                                                 area_entry.geofence_included)
        # geofence_excluded: Optional[SettingsGeofence] = None
        # if area_entry.geofence_excluded is not None:
        #    geofence_excluded: Optional[SettingsGeofence] = await SettingsGeofenceHelper.get(session, instance_id,
        #                                                                                     area_entry.geofence_excluded)
        if fence_type is not None and area_entry.settings.mode != fence_type:
            continue

        # area_geofences = GeofenceHelper(geofence_included, geofence_excluded, area_entry.settings.name)
        area_geofences: Optional[GeofenceHelper] = await mapping_manager.routemanager_get_geofence_helper(area_id)
        include = {}
        exclude = {}
        if area_geofences:
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
            'mode': area_entry.settings.mode,
            'area_id': area_id,
            'name': area_entry.settings.name
        }
    return geofences


async def generate_coords_from_geofence(mapping_manager: MappingManager, session: AsyncSession, instance_id: int,
                                        fence):
    fence_string = []
    geofences = await get_geofences(mapping_manager, session=session, instance_id=instance_id)
    coordinates = []
    for fences in geofences.values():
        for fname, coords in fences.get('include').items():
            if fname != fence:
                continue
            coordinates.append(coords)

    for coord in coordinates[0]:
        fence_string.append(str(coord[0]) + " " + str(coord[1]))

    fence_string.append(fence_string[0])
    return ",".join(fence_string)


async def get_quest_areas(mapping_manager: MappingManager, session: AsyncSession, instance_id: int):
    stop_fences = ['All']
    possible_fences = await get_geofences(mapping_manager, session, instance_id, fence_type='pokestops')
    for possible_fence in possible_fences:
        for subfence in possible_fences[possible_fence]['include']:
            if subfence in stop_fences:
                continue
            stop_fences.append(subfence)

    return stop_fences
