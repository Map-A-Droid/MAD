import glob
import os
from math import floor
from typing import Dict, List, Optional

from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.mapping_manager.MappingManager import (AreaEntry,
                                                      DeviceMappingsEntry,
                                                      MappingManager)
from mapadroid.updater.JobType import JobType
from mapadroid.updater.SubJob import SubJob
from mapadroid.utils.DatetimeWrapper import DatetimeWrapper
from mapadroid.utils.functions import creation_date
from mapadroid.utils.madGlobals import application_args
from mapadroid.worker.Worker import WorkerType


def allowed_file(filename):
    allowed_extensions = {'apk', 'txt'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


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


async def get_geofences(mapping_manager: MappingManager,
                        worker_type: Optional[WorkerType] = None,
                        area_id_req: Optional[int] = None) -> Dict[int, Dict]:
    # TODO: Request the geofence instances from the MappingManager directly?
    areas: Dict[int, AreaEntry] = await mapping_manager.get_areas()
    geofences = {}
    for area_id, area_entry in areas.items():
        if area_id_req is not None and area_id != area_id_req:
            continue
        if worker_type is not None and area_entry.settings.mode != worker_type.value:
            continue

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


async def generate_coords_from_geofence(mapping_manager: MappingManager,
                                        fence):
    fence_string = []
    geofences = await get_geofences(mapping_manager)
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


async def get_quest_areas(mapping_manager: MappingManager):
    stop_fences = ['All']
    possible_fences: Dict[int, Dict] = await get_geofences(mapping_manager, worker_type=WorkerType.STOPS)
    for possible_fence in possible_fences:
        for subfence in possible_fences[possible_fence]['include']:
            if subfence in stop_fences:
                continue
            stop_fences.append(subfence)

    return stop_fences
