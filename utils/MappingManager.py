import json
import os
import time
from queue import Empty, Queue
from multiprocessing import Lock, Event, Queue
from multiprocessing.managers import SyncManager
from multiprocessing.pool import ThreadPool
from pathlib import Path
from threading import Thread
from typing import Optional, List, Dict, Tuple

from db.dbWrapperBase import DbWrapperBase
from geofence.geofenceHelper import GeofenceHelper
from route import RouteManagerBase, RouteManagerIV
from route.RouteManagerFactory import RouteManagerFactory
from utils.collections import Location
from utils.logging import logger
from utils.s2Helper import S2Helper

mode_mapping = {
    "raids_mitm": {
        "s2_cell_level": 13,
        "range": 490,
        "range_init": 490,
        "max_count": 100000
    },
    "mon_mitm": {
        "s2_cell_level": 17,
        "range": 67,
        "range_init": 145,
        "max_count": 100000
    },
    "pokestops": {
        "s2_cell_level": 13,
        "range": 0.001,
        "range_init": 490,
        "max_count": 100000
    },
    "iv_mitm": {
        "range": 0,
        "range_init": 0,
        "max_count": 999999
    }
}


class JoinQueue(object):
    def __init__(self, stop_trigger, mapping_manager):
        self._joinqueue: Queue = Queue()
        self.__stop_file_watcher_event = stop_trigger
        self._mapping_mananger = mapping_manager
        self.__route_join_thread: Thread = Thread(name='route_joiner',
                                                  target=self.__route_join, )
        self.__route_join_thread.daemon = True
        self.__route_join_thread.start()

    def __route_join(self):
        logger.info("Starting Route join Thread - safemode")
        while not self.__stop_file_watcher_event.is_set():
            try:
                routejoin = self._joinqueue.get_nowait()
            except Empty as e:
                time.sleep(1)
                continue
            except (EOFError, KeyboardInterrupt) as e:
                logger.info("Route join thread noticed shutdown")
                return

            if routejoin is not None:
                self._mapping_mananger.routemanager_join(routejoin)

    def set_queue(self, item):
        self._joinqueue.put(item)


class MappingManagerManager(SyncManager):
    pass


class MappingManager:
    def __init__(self, db_wrapper: DbWrapperBase, args, configmode: bool = False):
        self.__db_wrapper: DbWrapperBase = db_wrapper
        self.__args = args
        self.__configmode: bool = configmode

        self._devicemappings: Optional[dict] = None
        self._areas: Optional[dict] = None
        self._routemanagers: Optional[Dict[str, dict]] = None
        self._auths: Optional[dict] = None
        self._monlists: Optional[dict] = None
        self.__stop_file_watcher_event: Event = Event()
        self.join_routes_queue = JoinQueue(self.__stop_file_watcher_event, self)
        self.__raw_json: Optional[dict] = None
        self.__mappings_mutex: Lock = Lock()

        self.update(full_lock=True)

        if self.__args.auto_reload_config:
            logger.info("Starting file watcher for mappings.json changes.")
            self.__t_file_watcher = Thread(name='file_watcher', target=self.__file_watcher,)
            self.__t_file_watcher.daemon = False
            self.__t_file_watcher.start()
        self.__devicesettings_setter_queue: Queue = Queue()
        self.__devicesettings_setter_consumer_thread: Thread = Thread(name='devicesettings_setter_consumer',
                                                                      target=self.__devicesettings_setter_consumer,)
        self.__devicesettings_setter_consumer_thread.daemon = True
        self.__devicesettings_setter_consumer_thread.start()

    def shutdown(self):
        logger.fatal("MappingManager exiting")
        self.__stop_file_watcher_event.set()
        self.__t_file_watcher.join()
        self.__devicesettings_setter_consumer_thread.join()

    def get_auths(self) -> Optional[dict]:
        return self._auths

    def get_devicemappings_of(self, device_name: str) -> Optional[dict]:
        return self._devicemappings.get(device_name, None)

    def set_devicemapping_value_of(self, device_name: str, key: str, value):
        with self.__mappings_mutex:
            if self._devicemappings.get(device_name, None) is not None:
                self._devicemappings[device_name][key] = value

    def get_devicesettings_of(self, device_name: str) -> Optional[dict]:
        return self._devicemappings.get(device_name, None).get('settings', None)

    def __devicesettings_setter_consumer(self):
        logger.info("Starting Devicesettings consumer Thread")
        while not self.__stop_file_watcher_event.is_set():
            try:
                set_settings = self.__devicesettings_setter_queue.get_nowait()
            except Empty as e:
                time.sleep(0.2)
                continue
            except (EOFError, KeyboardInterrupt) as e:
                logger.info("Devicesettings setter thread noticed shutdown")
                return

            if set_settings is not None:
                device_name, key, value = set_settings
                with self.__mappings_mutex:
                    if self._devicemappings.get(device_name, None) is not None:
                        if self._devicemappings[device_name].get("settings", None) is None:
                            self._devicemappings[device_name]["settings"] = {}
                        self._devicemappings[device_name]['settings'][key] = value

    def set_devicesetting_value_of(self, device_name: str, key: str, value):
        if self._devicemappings.get(device_name, None) is not None:
            self.__devicesettings_setter_queue.put((device_name, key, value))

    def get_all_devicemappings(self) -> Optional[dict]:
        return self._devicemappings

    def get_areas(self) -> Optional[dict]:
        return self._areas

    def get_monlist(self, listname, areaname):
        if type(listname) is list:
            logger.error('Area {} is using old list format instead of global mon list. Please check your mappings.json.'
                         ' Using empty list instead.'.format(str(areaname)))
            return []
        if listname is not None and listname in self._monlists:
            return self._monlists[listname]
        elif listname is None:
            return []
        else:
            logger.error("IV list '{}' has been used in area '{}' but does not exist. Using empty IV list instead.",
                         listname, areaname)
            return []

    def get_all_routemanager_names(self):
        return self._routemanagers.keys()

    def __fetch_routemanager(self, routemanager_name: str) -> Optional[RouteManagerBase.RouteManagerBase]:
        with self.__mappings_mutex:
            routemanager_dict: dict = self._routemanagers.get(routemanager_name, None)
            if routemanager_dict is not None:
                return routemanager_dict.get("routemanager")
            else:
                return None

    def routemanager_present(self, routemanager_name: str) -> bool:
        with self.__mappings_mutex:
            return routemanager_name in self._routemanagers.keys()

    def routemanager_get_next_location(self, routemanager_name: str, origin: str) -> Optional[Location]:
        routemanager = self.__fetch_routemanager(routemanager_name)
        return routemanager.get_next_location(origin) if routemanager is not None else None

    def routemanager_join(self, routemanager_name: str):
        routemanager = self.__fetch_routemanager(routemanager_name)
        if routemanager is not None:
            routemanager.join_threads()

    def routemanager_stop(self, routemanager_name: str):
        routemanager = self.__fetch_routemanager(routemanager_name)
        if routemanager is not None:
            routemanager.stop_routemanager()

    def register_worker_to_routemanager(self, routemanager_name: str, worker_name: str) -> bool:
        routemanager = self.__fetch_routemanager(routemanager_name)
        return routemanager.register_worker(worker_name) if routemanager is not None else False

    def unregister_worker_from_routemanager(self, routemanager_name: str, worker_name: str):
        routemanager = self.__fetch_routemanager(routemanager_name)
        return routemanager.unregister_worker(worker_name) if routemanager is not None else None

    def routemanager_add_coords_to_be_removed(self, routemanager_name: str, lat: float, lon: float):
        routemanager = self.__fetch_routemanager(routemanager_name)
        if routemanager is not None:
            routemanager.add_coord_to_be_removed(lat, lon)

    def routemanager_get_route_stats(self, routemanager_name: str, origin: str) -> Optional[Tuple[int, int]]:
        routemanager = self.__fetch_routemanager(routemanager_name)
        return routemanager.get_route_status(origin) if routemanager is not None else None

    def routemanager_get_rounds(self, routemanager_name: str, worker_name: str) -> Optional[int]:
        routemanager = self.__fetch_routemanager(routemanager_name)
        return routemanager.get_rounds(worker_name) if routemanager is not None else None

    def routemanager_redo_stop(self, routemanager_name: str, worker_name: str, lat: float, lon: float) -> bool:
        routemanager = self.__fetch_routemanager(routemanager_name)
        return routemanager.redo_stop(worker_name, lat, lon) if routemanager is not None else False

    def routemanager_get_registered_workers(self, routemanager_name: str) -> Optional[int]:
        routemanager = self.__fetch_routemanager(routemanager_name)
        return routemanager.get_registered_workers() if routemanager is not None else None

    def routemanager_get_ids_iv(self, routemanager_name: str) -> Optional[List[int]]:
        routemanager = self.__fetch_routemanager(routemanager_name)
        return routemanager.get_ids_iv() if routemanager is not None else None

    def routemanager_get_geofence_helper(self, routemanager_name: str) -> Optional[GeofenceHelper]:
        routemanager = self.__fetch_routemanager(routemanager_name)
        return routemanager.get_geofence_helper() if routemanager is not None else None

    def routemanager_get_init(self, routemanager_name: str) -> bool:
        routemanager = self.__fetch_routemanager(routemanager_name)
        return routemanager.get_init() if routemanager is not None else False

    def routemanager_get_level(self, routemanager_name: str) -> bool:
        routemanager = self.__fetch_routemanager(routemanager_name)
        return routemanager.get_level_mode() if routemanager is not None else None

    def routemanager_get_mode(self, routemanager_name: str) -> Optional[str]:
        routemanager = self.__fetch_routemanager(routemanager_name)
        return routemanager.get_mode() if routemanager is not None else None

    def routemanager_get_encounter_ids_left(self, routemanager_name: str) -> Optional[List[int]]:
        routemanager = self.__fetch_routemanager(routemanager_name)
        if routemanager is not None and isinstance(routemanager, RouteManagerIV.RouteManagerIV):
            return routemanager.get_encounter_ids_left()
        else:
            return None

    def routemanager_get_current_route(self, routemanager_name: str) -> Optional[List[Location]]:
        routemanager = self.__fetch_routemanager(routemanager_name)
        return routemanager.get_current_route() if routemanager is not None else None

    def routemanager_get_current_prioroute(self, routemanager_name: str) -> Optional[List[Location]]:
        routemanager = self.__fetch_routemanager(routemanager_name)
        return routemanager.get_current_prioroute() if routemanager is not None else None

    def routemanager_get_settings(self, routemanager_name: str) -> Optional[dict]:
        routemanager = self.__fetch_routemanager(routemanager_name)
        return routemanager.get_settings() if routemanager is not None else None

    def routemanager_set_worker_sleeping(self, routemanager_name: str, worker_name: str, sleep_duration: float):
        routemanager = self.__fetch_routemanager(routemanager_name)
        routemanager.set_worker_sleeping(worker_name, sleep_duration)

    def routemanager_get_position_type(self, routemanager_name: str, worker_name: str) -> Optional[str]:
        routemanager = self.__fetch_routemanager(routemanager_name)
        return routemanager.get_position_type(worker_name) if routemanager is not None else None

    def __read_mappings_file(self):
        with open(self.__args.mappings) as f:
            self.__raw_json = json.load(f)
            if 'walker' not in self.__raw_json:
                self.__raw_json['walker'] = []
            if 'devicesettings' not in self.__raw_json:
                self.__raw_json['devicesettings'] = []
            if 'monivlist' not in self.__raw_json:
                self.__raw_json['monivlist'] = []

    def __inherit_device_settings(self, devicesettings, poolsettings):
        inheritsettings = {}
        for set in poolsettings:
            inheritsettings[set] = poolsettings[set]
        for set in devicesettings:
            inheritsettings[set] = devicesettings[set]
        return inheritsettings

    def __get_latest_routemanagers(self) -> Optional[Dict[str, dict]]:
        global mode_mapping
        areas: Optional[Dict[str, dict]] = {}

        if self.__configmode:
            return areas

        area_arr = self.__raw_json["areas"]

        thread_pool = ThreadPool(processes=4)

        areas_procs = {}
        for area in area_arr:
            if area["geofence_included"] is None:
                raise RuntimeError("Cannot work without geofence_included")

            geofence_included = Path(area["geofence_included"])
            if not geofence_included.is_file():
                raise RuntimeError(
                        "geofence_included for area '{}' is specified but file does not exist ('{}').".format(
                                area["name"], geofence_included.resolve()
                        )
                )

            geofence_excluded_raw_path = area.get("geofence_excluded", None)
            if geofence_excluded_raw_path is not None:
                geofence_excluded = Path(geofence_excluded_raw_path)
                if not geofence_excluded.is_file():
                    raise RuntimeError(
                            "geofence_excluded for area '{}' is specified but file does not exist ('{}').".format(
                                    area["name"], geofence_excluded.resolve()
                            )
                    )

            area_dict = {"mode":              area["mode"],
                         "geofence_included": area["geofence_included"],
                         "geofence_excluded": area.get("geofence_excluded", None),
                         "routecalc":         area["routecalc"]}
            # also build a routemanager for each area...

            # grab coords
            # first check if init is false, if so, grab the coords from DB
            # coords = np.loadtxt(area["coords"], delimiter=',')
            geofence_helper = GeofenceHelper(
                    area["geofence_included"], area.get("geofence_excluded", None))
            mode = area["mode"]
            # build routemanagers

            #map iv list to ids
            if area.get('settings', None) is not None and 'mon_ids_iv' in area['settings']:
                # replace list name
                area['settings']['mon_ids_iv_raw'] = \
                    self.get_monlist(area['settings'].get('mon_ids_iv', None), area.get("name", "unknown"))

            route_manager = RouteManagerFactory.get_routemanager(self.__db_wrapper, None,
                                                                 mode_mapping.get(mode, {}).get("range", 0),
                                                                 mode_mapping.get(mode, {}).get("max_count", 99999999),
                                                                 area["geofence_included"],
                                                                 area.get("geofence_excluded", None),
                                                                 mode=mode, settings=area.get("settings", None),
                                                                 init=area.get("init", False),
                                                                 name=area.get("name", "unknown"),
                                                                 level=area.get("level", False),
                                                                 coords_spawns_known=area.get(
                                                                         "coords_spawns_known", False),
                                                                 routefile=area["routecalc"],
                                                                 calctype=area.get("route_calc_algorithm", "optimized"),
                                                                 joinqueue=self.join_routes_queue
                                                                 )

            if mode not in ("iv_mitm", "idle"):
                coords = self.__fetch_coords(mode, geofence_helper,
                                             coords_spawns_known=area.get("coords_spawns_known", False),
                                             init=area.get("init", False),
                                             range_init=mode_mapping.get(area["mode"], {}).get("range_init", 630),
                                             including_stops=area.get("including_stops", False))
                route_manager.add_coords_list(coords)
                max_radius = mode_mapping[area["mode"]]["range"]
                max_count_in_radius = mode_mapping[area["mode"]]["max_count"]
                if not area.get("init", False):
                    logger.info("Initializing area {}", area["name"])
                    proc = thread_pool.apply_async(route_manager.recalc_route, args=(max_radius, max_count_in_radius,
                                                                                     0, False))
                    areas_procs[area["name"]] = proc
                else:
                    logger.info(
                            "Init mode enabled. Going row-based for {}", str(area.get("name", "unknown")))
                    # we are in init, let's write the init route to file to make it visible in madmin
                    if area["routecalc"] is not None:
                        routefile = os.path.join(
                                self.__args.file_path, area["routecalc"])
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

            area_dict["routemanager"] = route_manager
            areas[area["name"]] = area_dict

        for area in areas_procs.keys():
            to_be_checked = areas_procs[area]
            to_be_checked.get()

        thread_pool.close()
        thread_pool.join()
        return areas

    def __get_latest_devicemappings(self) -> dict:
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
                        device_dict["settings"] = self.__inherit_device_settings(settings,
                                                                                 pool_arr[pool_settings]
                                                                                 .get('settings', []))
                        break
                    pool_settings += 1
            else:
                device_dict["settings"] = device.get("settings", None)

            if walker:
                walker_settings = 0
                while walker_settings < len(walker_arr):
                    if walker_arr[walker_settings]['walkername'] == walker:
                        device_dict["walker"] = walker_arr[walker_settings].get(
                            'setup', [])
                        break
                    walker_settings += 1
            devices[device["origin"]] = device_dict
        return devices

    def __fetch_coords(self, mode: str, geofence_helper: GeofenceHelper, coords_spawns_known: bool = False,
                       init: bool = False, range_init: int = 630, including_stops: bool = False) -> List[Location]:
        coords: List[Location] = []
        if not init:
            # grab data from DB depending on mode
            # TODO: move routemanagers to factory
            if mode == "raids_mitm":
                coords = self.__db_wrapper.gyms_from_db(geofence_helper)
                if including_stops:
                    coords.extend(self.__db_wrapper.stops_from_db(geofence_helper))
            elif mode == "mon_mitm":
                if coords_spawns_known:
                    logger.debug("Reading known Spawnpoints from DB")
                    coords = self.__db_wrapper.get_detected_spawns(geofence_helper)
                else:
                    logger.debug("Reading unknown Spawnpoints from DB")
                    coords = self.__db_wrapper.get_undetected_spawns(geofence_helper)
            elif mode == "pokestops":
                coords = self.__db_wrapper.stops_from_db(geofence_helper)
            else:
                logger.error("Mode not implemented yet: {}", str(mode))
                exit(1)
        else:
            # calculate all level N cells (mapping back from mapping above linked to mode)
            coords = S2Helper._generate_locations(range_init, geofence_helper)
        return coords

    def __get_latest_auths(self) -> Optional[dict]:
        """
        Reads current self.__raw_json mappings dict and checks if auth directive is present.
        :return: Dict of username : password
        """
        auth_arr = self.__raw_json.get("auth", None)
        if auth_arr is None or len(auth_arr) == 0:
            return None

        auths = {}
        for auth in auth_arr:
            auths[auth["username"]] = auth["password"]
        return auths

    def __get_latest_areas(self) -> dict:
        areas = {}
        areas_arr = self.__raw_json["areas"]
        for area in areas_arr:
            area_dict = {}
            area_dict['routecalc'] = area.get('routecalc', None)
            area_dict['mode'] = area['mode']
            area_dict['geofence_included'] = area.get(
                    'geofence_included', None)
            area_dict['geofence_excluded'] = area.get(
                    'geofence_excluded', None)
            area_dict['init'] = area.get('init', False)
            areas[area['name']] = area_dict
        return areas

    def __get_latest_monlists(self) -> dict:
        # {'mon_ids_iv': [787, 1], 'monlist': 'test'}
        monlist = {}
        monlists_arr = self.__raw_json["monivlist"]
        for list in monlists_arr:
            monlist[list['monlist']] = list.get('mon_ids_iv', None)
        return monlist

    def update(self, full_lock=False):
        """
        Updates the internal mappings and routemanagers
        :return:
        """
        self.__read_mappings_file()
        if not full_lock:
            self._monlists = self.__get_latest_monlists()
            areas_tmp = self.__get_latest_areas()
            devicemappings_tmp = self.__get_latest_devicemappings()
            routemanagers_tmp = self.__get_latest_routemanagers()
            auths_tmp = self.__get_latest_auths()

            for area in self._routemanagers:
                self._routemanagers[area]['routemanager'].stop_routemanager()

            logger.info("Restoring old devicesettings")
            for dev in self._devicemappings:
                if "last_location" in self._devicemappings[dev]['settings']:
                    devicemappings_tmp[dev]['settings']["last_location"] = \
                        self._devicemappings[dev]['settings']["last_location"]
                if "last_mode" in self._devicemappings[dev]['settings']:
                    devicemappings_tmp[dev]['settings']["last_mode"] = \
                        self._devicemappings[dev]['settings']["last_mode"]
                if "accountindex" in self._devicemappings[dev]['settings']:
                    devicemappings_tmp[dev]['settings']["accountindex"] = \
                        self._devicemappings[dev]['settings']["accountindex"]
                if "account_rotation_started" in self._devicemappings[dev]['settings']:
                    devicemappings_tmp[dev]['settings']["account_rotation_started"] = \
                        self._devicemappings[dev]['settings']["account_rotation_started"]

            logger.info("Acquiring lock to update mappings")
            with self.__mappings_mutex:
                self._areas = areas_tmp
                self._devicemappings = devicemappings_tmp
                self._routemanagers = routemanagers_tmp
                self._auths = auths_tmp

        else:
            logger.info("Acquiring lock to update mappings,full")
            with self.__mappings_mutex:
                self._monlists = self.__get_latest_monlists()
                self._routemanagers = self.__get_latest_routemanagers()
                self._areas = self.__get_latest_areas()
                self._devicemappings = self.__get_latest_devicemappings()
                self._auths = self.__get_latest_auths()

        logger.info("Mappings have been updated")

    def __file_watcher(self):
        # We're on a 20-second timer.
        refresh_time_sec = int(self.__args.auto_reload_delay)
        filename = self.__args.mappings
        logger.info('Mappings.json reload delay: {} seconds', refresh_time_sec)

        while not self.__stop_file_watcher_event.is_set():
            # Wait (x-1) seconds before refresh, min. 1s.
            try:
                time.sleep(max(1, refresh_time_sec - 1))
            except KeyboardInterrupt:
                logger.info("Mappings.json watch got interrupted, stopping")
                break
            try:
                # Only refresh if the file has changed.
                current_time_sec = time.time()
                file_modified_time_sec = os.path.getmtime(filename)
                time_diff_sec = current_time_sec - file_modified_time_sec

                # File has changed in the last refresh_time_sec seconds.
                if time_diff_sec < refresh_time_sec:
                    logger.info(
                            'Change found in {}. Updating device mappings.', filename)
                    self.update()
                else:
                    logger.debug('No change found in {}.', filename)
            except KeyboardInterrupt as e:
                logger.info("Got interrupt signal, stopping watching mappings.json")
                break
            except Exception as e:
                logger.exception(
                        'Exception occurred while updating device mappings: {}.', e)

    def get_all_devices(self):
        devices = []
        device_arr = self.__raw_json["devices"]
        for device in device_arr:
            devices.append(device['origin'])

        return devices
