import json
import logging
import os
import sys
from pathlib import Path

from geofence.geofenceHelper import GeofenceHelper
from route.RouteManagerIV import RouteManagerIV
from route.RouteManagerMon import RouteManagerMon
from route.RouteManagerRaids import RouteManagerRaids
from utils.s2Helper import S2Helper

log = logging.getLogger(__name__)

mode_mapping = {
    "raids_mitm": {
        "s2_cell_level": 13,
        "range": 610,
        "max_count": 100000
    },
    "mon_mitm": {
        "s2_cell_level": 17,
        "range": 67,
        "max_count": 100000
    },
    "raids_ocr": {
        "range": 610,
        "max_count": 7
    },
    "pokestops": {
        "s2_cell_level": 13,
        "range": 1,
        "max_count": 100000
    }
}


class MappingParser(object):
    def __init__(self, db_wrapper):
        self.db_wrapper = db_wrapper
        with open('configs/mappings.json') as f:
            self.__raw_json = json.load(f)

    def get_routemanagers(self):
        from multiprocessing.pool import ThreadPool
        global mode_mapping

        # returns list of routemanagers with area IDs
        areas = {}
        area_arr = self.__raw_json["areas"]

        thread_pool = ThreadPool(processes=4)

        areas_procs = {}
        for area in area_arr:
            if area["geofence_included"] is None:
                raise RuntimeError("Cannot work without geofence_included")

            geofence_included = Path(area["geofence_included"])
            if not geofence_included.is_file():
                log.error("Geofence included file configured does not exist")
                sys.exit(1)

            geofence_excluded_raw_path = area.get("geofence_excluded", None)
            if geofence_excluded_raw_path is not None:
                geofence_excluded = Path(geofence_excluded_raw_path)
                if not geofence_excluded.is_file():
                    log.error("Geofence excluded specified but does not exist")
                    sys.exit(1)

            area_dict = {"mode": area["mode"],
                         "geofence_included": area["geofence_included"],
                         "geofence_excluded": area.get("geofence_excluded", None),
                         "routecalc": area["routecalc"]}
            # also build a routemanager for each area...

            # grab coords
            # first check if init is false or raids_ocr is set as mode, if so, grab the coords from DB
            # coords = np.loadtxt(area["coords"], delimiter=',')
            geofence_helper = GeofenceHelper(
                area["geofence_included"], area.get("geofence_excluded", None))
            mode = area["mode"]
            # build routemanagers
            if mode == "raids_ocr" or mode == "raids_mitm":
                route_manager = RouteManagerRaids(self.db_wrapper, None, mode_mapping[area["mode"]]["range"],
                                                  mode_mapping[area["mode"]
                                                               ]["max_count"],
                                                  area["geofence_included"], area.get(
                                                      "geofence_excluded", None),
                                                  area["routecalc"],
                                                  mode=area["mode"], settings=area.get(
                                                      "settings", None),
                                                  init=area.get("init", False),
                                                  name=area.get(
                                                      "name", "unknown")
                                                  )
            elif mode == "mon_mitm":
                route_manager = RouteManagerMon(self.db_wrapper, None, mode_mapping[area["mode"]]["range"],
                                                mode_mapping[area["mode"]
                                                             ]["max_count"],
                                                area["geofence_included"], area.get(
                                                    "geofence_excluded", None),
                                                area["routecalc"], mode=area["mode"],
                                                coords_spawns_known=area.get(
                                                    "coords_spawns_known", False),
                                                init=area.get("init", False),
                                                name=area.get(
                                                    "name", "unknown"),
                                                settings=area.get(
                                                    "settings", None)
                                                )
            elif mode == "iv_mitm":
                route_manager = RouteManagerIV(self.db_wrapper, None, 0, 999999,
                                               area["geofence_included"], area.get(
                                                   "geofence_excluded", None),
                                               area["routecalc"], name=area.get(
                                                   "name", "unknown"),
                                               settings=area.get(
                                                   "settings", None),
                                               mode=mode
                                               )
            elif mode == "pokestops":
                route_manager = RouteManagerMon(self.db_wrapper, None, mode_mapping[area["mode"]]["range"],
                                                mode_mapping[area["mode"]
                                                             ]["max_count"],
                                                area["geofence_included"], area.get(
                                                    "geofence_excluded", None),
                                                area["routecalc"], mode=area["mode"],
                                                init=area.get("init", False),
                                                name=area.get(
                                                    "name", "unknown"),
                                                settings=area.get(
                                                    "settings", None)
                                                )
            else:
                log.error("Invalid mode found in mapping parser.")
                sys.exit(1)

            if not mode == "iv_mitm":
                if mode == "raids_ocr" or area.get("init", False) is False:
                    # grab data from DB depending on mode
                    # TODO: move routemanagers to factory
                    if mode == "raids_ocr" or mode == "raids_mitm":
                        coords = self.db_wrapper.gyms_from_db(geofence_helper)
                    elif mode == "mon_mitm":
                        spawn_known = area.get("coords_spawns_known", False)
                        if spawn_known:
                            log.info("Reading known Spawnpoints from DB")
                            coords = self.db_wrapper.get_detected_spawns(
                                geofence_helper)
                        else:
                            log.info("Reading unknown Spawnpoints from DB")
                            coords = self.db_wrapper.get_undetected_spawns(
                                geofence_helper)
                    elif mode == "pokestops":
                        coords = self.db_wrapper.stops_from_db(geofence_helper)
                    else:
                        log.fatal("Mode not implemented yet: %s" % str(mode))
                        exit(1)
                else:
                    # calculate all level N cells (mapping back from mapping above linked to mode)
                    # coords = S2Helper.get_s2_cells_from_fence(geofence=geofence_helper,
                    #                                           cell_size=mode_mapping[mode]["s2_cell_level"])
                    coords = S2Helper._generate_locations(mode_mapping[area["mode"]]["range"],
                                                          geofence_helper)

                route_manager.add_coords_list(coords)
                max_radius = mode_mapping[area["mode"]]["range"]
                max_count_in_radius = mode_mapping[area["mode"]]["max_count"]
                if not area.get("init", False):
                    log.info("Calculating route for %s" %
                             str(area.get("name", "unknown")))
                    proc = thread_pool.apply_async(route_manager.recalc_route, args=(max_radius, max_count_in_radius,
                                                                                     0, False))
                    areas_procs[area["name"]] = proc
                else:
                    log.info("Init mode enabled and more than 400 coords in init. Going row-based for %s"
                             % str(area.get("name", "unknown")))
                    # we are in init, let's write the init route to file to make it visible in madmin
                    if area["routecalc"] is not None:
                        routefile = area["routecalc"]
                        if os.path.isfile(routefile + '.calc'):
                            os.remove(routefile + '.calc')
                        with open(routefile + '.calc', 'a') as f:
                            for loc in coords:
                                f.write(str(loc.lat) + ', ' +
                                        str(loc.lng) + '\n')
                    # gotta feed the route to routemanager... TODO: without recalc...
                    proc = thread_pool.apply_async(route_manager.recalc_route, args=(1, 99999999,
                                                                                     0, False))
                    areas_procs[area["name"]] = proc
            # log.error("Calculated route, appending another coord and recalculating")

            area_dict["routemanager"] = route_manager
            areas[area["name"]] = area_dict

        for area in areas_procs.keys():
            to_be_checked = areas_procs[area]
            log.debug(to_be_checked)
            to_be_checked.get()

        thread_pool.close()
        thread_pool.join()
        return areas

    def get_devicemappings(self):
        # returns mapping of devises to areas
        devices = {}
        device_arr = self.__raw_json["devices"]
        for device in device_arr:
            device_dict = {}
            daytime_area = device["daytime_area"]
            nighttime_area = device.get("nighttime_area", None)
            switch = device.get("switch", False)
            switch_interval = device.get("switch_interval", False)
            settings = device.get("settings", None)
            device_dict["daytime_area"] = daytime_area
            device_dict["nighttime_area"] = nighttime_area
            device_dict["switch"] = switch
            device_dict["switch_interval"] = switch_interval
            device_dict["settings"] = settings
            devices[device["origin"]] = device_dict
        return devices

    def get_auths(self):
        # returns list of allowed authentications
        auth_arr = self.__raw_json.get("auth", None)
        if auth_arr is None or len(auth_arr) == 0:
            return None

        auths = {}
        for auth in auth_arr:
            auths[auth["username"]] = auth["password"]
        return auths
