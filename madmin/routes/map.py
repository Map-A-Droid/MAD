import json
import os
from typing import List, Optional

from flask import (jsonify, render_template, request, redirect)
from flask_caching import Cache

from db.dbWrapperBase import DbWrapperBase
from madmin.functions import (auth_required, getCoordFloat, getBoundParameter,
                              getBasePath, get_geofences, generate_coords_from_geofence)
from utils.MappingManager import MappingManager
from utils.collections import Location
from utils.gamemechanicutil import get_raid_boss_cp
from utils.questGen import generate_quest
from utils.s2Helper import S2Helper
from utils.logging import logger

cache = Cache(config={'CACHE_TYPE': 'simple'})


class map(object):
    def __init__(self, db: DbWrapperBase, args, mapping_manager: MappingManager, app):
        self._db: DbWrapperBase = db
        self._args = args
        self._app = app
        if self._args.madmin_time == "12":
            self._datetimeformat = '%Y-%m-%d %I:%M:%S %p'
        else:
            self._datetimeformat = '%Y-%m-%d %H:%M:%S'

        self._mapping_manager: MappingManager = mapping_manager

        cache.init_app(self._app)
        self.add_route()

    def add_route(self):
        routes = [
            ("/map", self.map),
            ("/get_position", self.get_position),
            ("/get_geofence", self.get_geofence),
            ("/get_route", self.get_route),
            ("/get_prioroute", self.get_prioroute),
            ("/get_spawns", self.get_spawns),
            ("/get_gymcoords", self.get_gymcoords),
            ("/get_quests", self.get_quests),
            ("/get_map_mons", self.get_map_mons),
            ("/get_cells", self.get_cells),
            ("/savefence", self.savefence)
        ]
        for route, view_func in routes:
            self._app.route(route)(view_func)

    @auth_required
    def map(self):
        setlat = request.args.get('lat', 0)
        setlng = request.args.get('lng', 0)
        return render_template('map.html', lat=self._args.home_lat, lng=self._args.home_lng,
                               setlat=setlat, setlng=setlng)

    @auth_required
    def get_position(self):
        positions = []
        devicemappings = self._mapping_manager.get_all_devicemappings()
        for name, values in devicemappings.items():
            lat = values.get("settings").get("last_location", Location(0.0, 0.0)).lat
            lon = values.get("settings").get("last_location", Location(0.0, 0.0)).lng

            worker = {
                "name": str(name),
                "lat": getCoordFloat(lat),
                "lon": getCoordFloat(lon)
            }
            positions.append(worker)

        return jsonify(positions)

    @auth_required
    def get_geofence(self):
        geofences = {}

        geofences = get_geofences(self._mapping_manager)

        geofencexport = []
        for name, fences in geofences.items():
            coordinates = []
            for fname, coords in fences.get('include').items():
                coordinates.append([coords, fences.get('exclude').get(fname, [])])
            geofencexport.append({'name': name, 'coordinates': coordinates})

        return jsonify(geofencexport)

    @auth_required
    def get_route(self):
        routeexport = []

        routemanager_names = self._mapping_manager.get_all_routemanager_names()

        for routemanager in routemanager_names:
            mode = self._mapping_manager.routemanager_get_mode(routemanager)
            route: Optional[List[Location]] = self._mapping_manager.routemanager_get_current_route(routemanager)

            if route is None:
                continue
            route_serialized = []

            for location in route:
                route_serialized.append([
                    getCoordFloat(location.lat), getCoordFloat(location.lng)
                ])
            routeexport.append({
                "name": routemanager,
                "mode": mode,
                "coordinates": route_serialized
            })

        return jsonify(routeexport)

    @auth_required
    def get_prioroute(self):
        routeexport = []

        routemanager_names = self._mapping_manager.get_all_routemanager_names()

        for routemanager in routemanager_names:
            mode = self._mapping_manager.routemanager_get_mode(routemanager)
            route: Optional[List[Location]] = self._mapping_manager.routemanager_get_current_prioroute(routemanager)

            if route is None:
                continue
            route_serialized = []

            for location in route:
                route_serialized.append({
                    "timestamp": location[0],
                    "latitude": getCoordFloat(location[1].lat),
                    "longitude": getCoordFloat(location[1].lng)
                })

            routeexport.append({
                "name": routemanager,
                "mode": mode,
                "coordinates": route_serialized
            })

        return jsonify(routeexport)

    @auth_required
    def get_spawns(self):
        neLat, neLon, swLat, swLon, oNeLat, oNeLon, oSwLat, oSwLon = getBoundParameter(request)
        timestamp = request.args.get("timestamp", None)

        coords = []
        data = json.loads(
            self._db.download_spawns(
                neLat,
                neLon,
                swLat,
                swLon,
                oNeLat=oNeLat,
                oNeLon=oNeLon,
                oSwLat=oSwLat,
                oSwLon=oSwLon,
                timestamp=timestamp
            )
        )

        for spawnid in data:
            spawn = data[str(spawnid)]
            coords.append({
                "id": spawn["id"],
                "endtime": spawn["endtime"],
                "lat": spawn["lat"],
                "lon": spawn["lon"],
                "spawndef": spawn["spawndef"],
                "lastnonscan": spawn["lastnonscan"],
                "lastscan": spawn["lastscan"],
                "first_detection": spawn["first_detection"]
            })

        return jsonify(coords)

    @auth_required
    def get_gymcoords(self):
        neLat, neLon, swLat, swLon, oNeLat, oNeLon, oSwLat, oSwLon = getBoundParameter(request)
        timestamp = request.args.get("timestamp", None)

        coords = []

        data = self._db.get_gyms_in_rectangle(
            neLat,
            neLon,
            swLat,
            swLon,
            oNeLat=oNeLat,
            oNeLon=oNeLon,
            oSwLat=oSwLat,
            oSwLon=oSwLon,
            timestamp=timestamp
        )

        for gymid in data:
            gym = data[str(gymid)]

            coords.append({
                "id": gymid,
                "name": gym["name"],
                "img": gym["url"],
                "lat": gym["latitude"],
                "lon": gym["longitude"],
                "team_id": gym["team_id"],
                "last_updated": gym["last_updated"],
                "last_scanned": gym["last_scanned"],
                "raid": gym["raid"]
            })

        return jsonify(coords)

    @auth_required
    def get_quests(self):
        coords = []

        fence = request.args.get("fence", None)
        if fence not in (None, 'None', 'All'):
            fence = generate_coords_from_geofence(self._mapping_manager, fence)
        else:
            fence = None


        neLat, neLon, swLat, swLon, oNeLat, oNeLon, oSwLat, oSwLon = getBoundParameter(request)
        timestamp = request.args.get("timestamp", None)

        data = self._db.quests_from_db(
            neLat=neLat,
            neLon=neLon,
            swLat=swLat,
            swLon=swLon,
            oNeLat=oNeLat,
            oNeLon=oNeLon,
            oSwLat=oSwLat,
            oSwLon=oSwLon,
            timestamp=timestamp,
            fence=fence
        )

        for stopid in data:
            quest = data[str(stopid)]
            coords.append(generate_quest(quest))

        return jsonify(coords)

    @auth_required
    def get_map_mons(self):
        import traceback
        neLat, neLon, swLat, swLon, oNeLat, oNeLon, oSwLat, oSwLon = getBoundParameter(request)
        timestamp = request.args.get("timestamp", None)

        data = self._db.get_mons_in_rectangle(
            neLat=neLat,
            neLon=neLon,
            swLat=swLat,
            swLon=swLon,
            oNeLat=oNeLat,
            oNeLon=oNeLon,
            oSwLat=oSwLat,
            oSwLon=oSwLon,
            timestamp=timestamp
        )

        mons_raw = {}

        for i, mon in enumerate(data):
            try:
                id = data[i]["mon_id"]
                if str(id) in mons_raw:
                    mon_raw = mons_raw[str(id)]
                else:
                    mon_raw = get_raid_boss_cp(id)
                    mons_raw[str(id)] = mon_raw

                data[i]["encounter_id"] = str(data[i]["encounter_id"])
                data[i]["name"] = mon_raw["name"]
            except Exception:
                traceback.print_exc()

        return jsonify(data)

    @auth_required
    def get_cells(self):
        neLat, neLon, swLat, swLon, oNeLat, oNeLon, oSwLat, oSwLon = getBoundParameter(request)
        timestamp = request.args.get("timestamp", None)

        data = self._db.get_cells_in_rectangle(
            neLat=neLat,
            neLon=neLon,
            swLat=swLat,
            swLon=swLon,
            oNeLat=oNeLat,
            oNeLon=oNeLon,
            oSwLat=oSwLat,
            oSwLon=oSwLon,
            timestamp=timestamp
        )

        ret = []
        for cell in data:
            ret.append({
                "id": str(cell["id"]),
                "polygon": S2Helper.coords_of_cell(cell["id"]),
                "updated": cell["updated"]
            })

        return jsonify(ret)

    @logger.catch()
    @auth_required
    def savefence(self):
        name = request.args.get('name', False)
        coords = request.args.get('coords', False)

        if not name and not coords:
            return redirect(getBasePath(request) + "/map", code=302)

        coords_split = coords.split("|")
        geofence_file_path = self._args.geofence_file_path

        file = open(os.path.join(geofence_file_path, (str(name) + ".txt")), "a")
        file.write("[" + str(name) + "]\n")
        for i in range(len(coords_split)):
            if coords_split[i] != '':
                latlon_split = coords_split[i].split(",")
                file.write("{0},{1}\n".format(str(float(latlon_split[0])), str(float(latlon_split[1]))))

        file.close()

        return redirect(getBasePath(request) + "/map", code=302)
