import json
import os
from pathlib import Path
from loguru import logger

from geofence.geofenceHelper import GeofenceHelper
from route.RouteManagerIV import RouteManagerIV
from route.RouteManagerMon import RouteManagerMon
from route.RouteManagerQuests import RouteManagerQuests
from route.RouteManagerRaids import RouteManagerRaids
from utils.s2Helper import S2Helper

mode_mapping = {
    "raids_mitm": {
        "s2_cell_level": 13,
        "range":         490,
        "range_init":    490,
        "max_count":     100000

    },
    "mon_mitm":   {
        "s2_cell_level": 17,
        "range":         67,
        "range_init":    67,
        "max_count":     100000
    },
    "raids_ocr": {
        "range":         490,
        "range_init":    490,
        "max_count":     7
    },
    "pokestops":  {
        "s2_cell_level": 13,
        "range":         1,
        "range_init":    490,
        "max_count":     100000
    }
}


class MappingParser(object):
    def __init__(self, db_wrapper, configmode = False):
        self.db_wrapper = db_wrapper
        self.configmode = configmode
        with open('configs/mappings.json') as f:
            self.__raw_json = json.load(f)
            if 'walker' not in self.__raw_json: self.__raw_json['walker'] = []
            if 'devicesettings' not in self.__raw_json: self.__raw_json['devicesettings'] = []

    def get_routemanagers(self):
        from multiprocessing.pool import ThreadPool
        global mode_mapping

        # returns list of routemanagers with area IDs
        areas = {}

        if self.configmode:
            return areas

        area_arr = self.__raw_json["areas"]

        thread_pool = ThreadPool(processes=4)

        areas_procs = {}
        for area in area_arr:
            if area["geofence_included"] is None:
                raise RuntimeError("Cannot work without geofence_included")

            geofence_included = Path(area["geofence_included"])
            if not geofence_included.is_file():
                raise RuntimeError("Geofence included file for '{}' does not exist.".format(area["name"]))

            geofence_excluded_raw_path = area.get("geofence_excluded", None)
            if geofence_excluded_raw_path is not None:
                geofence_excluded = Path(geofence_excluded_raw_path)
                if not geofence_excluded.is_file():
                    raise RuntimeError("Geofence excluded file is specified but does not exist")

            area_dict = {"mode":              area["mode"],
                         "geofence_included": area["geofence_included"],
                         "geofence_excluded": area.get("geofence_excluded", None),
                         "routecalc":         area["routecalc"]}
            # also build a routemanager for each area...

            # grab coords
            # first check if init is false or raids_ocr is set as mode, if so, grab the coords from DB
            # coords = np.loadtxt(area["coords"], delimiter=',')
            geofence_helper = GeofenceHelper(area["geofence_included"], area.get("geofence_excluded", None))
            mode = area["mode"]
            # build routemanagers
            if mode == "raids_ocr" or mode == "raids_mitm":
                route_manager = RouteManagerRaids(self.db_wrapper, None, mode_mapping[area["mode"]]["range"],
                                                  mode_mapping[area["mode"]]["max_count"],
                                                  area["geofence_included"], area.get("geofence_excluded", None),
                                                  area["routecalc"],
                                                  mode=area["mode"], settings=area.get("settings", None),
                                                  init=area.get("init", False),
                                                  name=area.get("name", "unknown")
                                                  )
            elif mode == "mon_mitm":
                route_manager = RouteManagerMon(self.db_wrapper, None, mode_mapping[area["mode"]]["range"],
                                                mode_mapping[area["mode"]]["max_count"],
                                                area["geofence_included"], area.get("geofence_excluded", None),
                                                area["routecalc"], mode=area["mode"],
                                                coords_spawns_known=area.get("coords_spawns_known", False),
                                                init=area.get("init", False),
                                                name=area.get("name", "unknown"),
                                                settings=area.get("settings", None)
                                                )
            elif mode == "iv_mitm":
                route_manager = RouteManagerIV(self.db_wrapper, None, 0, 999999,
                                               area["geofence_included"], area.get("geofence_excluded", None),
                                               area["routecalc"], name=area.get("name", "unknown"),
                                               settings=area.get("settings", None),
                                               mode=mode
                                               )
            elif mode == "pokestops":
                route_manager = RouteManagerQuests(self.db_wrapper, None, mode_mapping[area["mode"]]["range"],
                                                   mode_mapping[area["mode"]]["max_count"],
                                                   area["geofence_included"], area.get("geofence_excluded", None),
                                                   area["routecalc"], mode=area["mode"],
                                                   init=area.get("init", False),
                                                   name=area.get("name", "unknown"),
                                                   settings=area.get("settings", None)
                                                   )
            else:
                raise RuntimeError("Invalid mode found in mapping parser.")

            if not mode == "iv_mitm":
                if mode == "raids_ocr" or area.get("init", False) is False:
                    # grab data from DB depending on mode
                    # TODO: move routemanagers to factory
                    if mode == "raids_ocr" or mode == "raids_mitm":
                        coords = self.db_wrapper.gyms_from_db(geofence_helper)
                    elif mode == "mon_mitm":
                        spawn_known = area.get("coords_spawns_known", False)
                        if spawn_known:
                            logger.debug("Reading known Spawnpoints from DB")
                            coords = self.db_wrapper.get_detected_spawns(geofence_helper)
                        else:
                            logger.debug("Reading unknown Spawnpoints from DB")
                            coords = self.db_wrapper.get_undetected_spawns(geofence_helper)
                    elif mode == "pokestops":
                        coords = self.db_wrapper.stops_from_db(geofence_helper)
                    else:
                        logger.error("Mode not implemented yet: {}", str(mode))
                        exit(1)
                else:
                    # calculate all level N cells (mapping back from mapping above linked to mode)
                    # coords = S2Helper.get_s2_cells_from_fence(geofence=geofence_helper,
                    #                                           cell_size=mode_mapping[mode]["s2_cell_level"])
                    coords = S2Helper._generate_locations(mode_mapping[area["mode"]]["range_init"],
                                                          geofence_helper)

                route_manager.add_coords_list(coords)
                max_radius = mode_mapping[area["mode"]]["range"]
                max_count_in_radius = mode_mapping[area["mode"]]["max_count"]
                if not area.get("init", False):
                    logger.info("Initializing area {}", area["name"])
                    proc = thread_pool.apply_async(route_manager.recalc_route, args=(max_radius, max_count_in_radius,
                                                                                     0, False))
                    areas_procs[area["name"]] = proc
                else:
                    logger.info("Init mode enabled and more than 400 coords in init. Going row-based for {}", str(area.get("name", "unknown")))
                    # we are in init, let's write the init route to file to make it visible in madmin
                    if area["routecalc"] is not None:
                        routefile = area["routecalc"]
                        if os.path.isfile(routefile + '.calc'):
                            os.remove(routefile + '.calc')
                        with open(routefile + '.calc', 'a') as f:
                            for loc in coords:
                                f.write(str(loc.lat) + ', ' + str(loc.lng) + '\n')
                    # gotta feed the route to routemanager... TODO: without recalc...
                    proc = thread_pool.apply_async(route_manager.recalc_route, args=(1, 99999999,
                                                                                     0, False))
                    areas_procs[area["name"]] = proc
            # logger.error("Calculated route, appending another coord and recalculating")

            area_dict["routemanager"] = route_manager
            areas[area["name"]] = area_dict

        for area in areas_procs.keys():
            to_be_checked = areas_procs[area]
            to_be_checked.get()

        thread_pool.close()
        thread_pool.join()
        return areas

    def get_devicemappings(self):
        # returns mapping of devises to areas
        devices = {}
        devices.clear()

        device_arr = self.__raw_json["devices"]
        walker_arr = self.__raw_json["walker"]
        pool_arr = self.__raw_json["devicesettings"]
        for device in device_arr:
            device_dict = {}
            device_dict.clear()
            walker = device["walker"]
            device_dict["adb"] = device.get("adbname", None)
            pool = device.get("pool", None)
            settings = device.get("settings", None)
            if pool:
                pool_settings = 0
                while pool_settings < len(pool_arr):
                    if pool_arr[pool_settings]['devicepool'] == pool:
                        device_dict["settings"] = self.inherit_device_settings(settings,
                                                                 pool_arr[pool_settings].get('settings', []))
                        break
                    pool_settings += 1
            else:
                device_dict["settings"] = device.get("settings", None)
                
            if walker:
                walker_settings = 0
                while walker_settings < len(walker_arr):
                    if walker_arr[walker_settings]['walkername'] == walker:
                        device_dict["walker"] = walker_arr[walker_settings].get('setup', [])
                        break
                    walker_settings += 1
            devices[device["origin"]] = device_dict
        return devices

    def inherit_device_settings(self, devicesettings, poolsettings):
        inheritsettings = {}
        for set in poolsettings:
            inheritsettings[set] = poolsettings[set]
        for set in devicesettings:
            inheritsettings[set] = devicesettings[set]
        return inheritsettings

    def get_auths(self):
        # returns list of allowed authentications
        auth_arr = self.__raw_json.get("auth", None)
        if auth_arr is None or len(auth_arr) == 0:
            return None

        auths = {}
        for auth in auth_arr:
            auths[auth["username"]] = auth["password"]
        return auths

    def get_areas(self):
        areas = {}
        areas_arr = self.__raw_json["areas"]
        for area in areas_arr:
            area_dict = {}
            area_dict['routecalc'] = area['routecalc']
            area_dict['mode'] = area['mode']
            area_dict['geofence_included'] = area['geofence_included']
            area_dict['geofence_excluded'] = area.get('geofence_excluded', None)
            area_dict['init'] = area.get('init', False)
            areas[area['name']] = area_dict
        return areas
