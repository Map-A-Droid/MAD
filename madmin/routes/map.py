import json
import os
from flask import (Flask, jsonify, render_template, request)
from flask_caching import Cache
from madmin.functions import auth_required, getCoordFloat, getBoundParameter
from utils.questGen import generate_quest
from pathlib import Path
from utils.mappingParser import MappingParser

cache = Cache(config={'CACHE_TYPE': 'simple'})


class map(object):
    def __init__(self, db, args, mapping_parser, app):
        self._db = db
        self._args = args
        self._app = app
        if self._args.madmin_time == "12":
            self._datetimeformat = '%Y-%m-%d %I:%M:%S %p'
        else:
            self._datetimeformat = '%Y-%m-%d %H:%M:%S'

        self._mapping_parser = mapping_parser
        self._device_mapping = self._mapping_parser.get_devicemappings()
        self._areas = self._mapping_parser.get_areas()

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
            ("/get_quests", self.get_quests)
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

        for name, device in self._device_mapping.items():
            try:
                with open(os.path.join(self._args.file_path, name + '.position'), 'r') as f:
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

    @auth_required
    def get_geofence(self):
        geofences = {}

        for name, area in self._areas.items():
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

        for name, area in self._areas.items():
            route = []
            try:
                with open(os.path.join(self._args.file_path, area['routecalc'] + '.calc'), 'r') as f:
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
