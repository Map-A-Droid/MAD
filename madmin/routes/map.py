import json
import os
from typing import List, Optional

from flask import (Flask, jsonify, render_template, request)
from flask_caching import Cache

from db.dbWrapperBase import DbWrapperBase
from madmin.functions import auth_required, getCoordFloat, getBoundParameter
from utils.MappingManager import MappingManager
from utils.collections import Location
from utils.questGen import generate_quest
from pathlib import Path
from utils.mappingParser import MappingParser

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
            ("/get_spawns", self.get_spawns),
            ("/get_gymcoords", self.get_gymcoords),
            ("/get_quests", self.get_quests),
            ("/get_nearby_mon", self.get_nearby_mon)
        ]
        for route, view_func in routes:
            self._app.route(route)(view_func)

    @auth_required
    def map(self):
        setlat = request.args.get('lat', 0)
        setlng = request.args.get('lng', 0)
        return render_template('map.html', lat=self._args.home_lat, lng=self._args.home_lng,
                               running_ocr=self._args.only_ocr, setlat=setlat, setlng=setlng)

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
            # try:
            #     with open(os.path.join(self._args.file_path, name + '.position'), 'r') as f:
            #         latlon = f.read().strip().split(', ')
            #         worker = {
            #             'name': str(name),
            #             'lat': getCoordFloat(latlon[0]),
            #             'lon': getCoordFloat(latlon[1])
            #         }
            #         positions.append(worker)
            # except OSError:
            #     pass

        return jsonify(positions)

    @auth_required
    def get_geofence(self):
        geofences = {}

        areas = self._mapping_manager.get_areas()
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

    @auth_required
    def get_route(self):
        routeexport = []

        routemanager_names = self._mapping_manager.get_all_routemanager_names()

        # areas = self._mapping_manager.get_areas()
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
                "lastscan": spawn["lastscan"]
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
            timestamp=timestamp
        )

        for pokestopid in data:
            quest = data[str(pokestopid)]
            coords.append(generate_quest(quest))

        return jsonify(coords)

    @auth_required
    def get_nearby_mon(self):
        coords = []

        neLat, neLon, swLat, swLon, oNeLat, oNeLon, oSwLat, oSwLon = getBoundParameter(request)
        timestamp = request.args.get("timestamp", None)

        data = self._db.get_nearbymon_in_rectangle(
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

        for encounter in data:
            mon = data[str(encounter)]

            coords.append({
                "encounter": encounter,
                "mon_id": mon["mon"],
                "lat": mon["latitude"],
                "lon": mon["longitude"],
            })

        return jsonify(coords)
