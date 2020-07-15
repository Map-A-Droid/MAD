import time
from multiprocessing import Lock, Event
from multiprocessing.managers import SyncManager
from multiprocessing.pool import ThreadPool
from queue import Empty, Queue
from threading import Thread
from typing import Optional, List, Dict, Tuple, Set
from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.route import RouteManagerIV, RouteManagerBase
from mapadroid.route.RouteManagerFactory import RouteManagerFactory
from mapadroid.utils.collections import Location
from mapadroid.utils.s2Helper import S2Helper
from mapadroid.worker.WorkerType import WorkerType
from mapadroid.utils.logging import get_logger, LoggerEnums


logger = get_logger(LoggerEnums.utils)

mode_mapping = {
    "raids_mitm": {
        "s2_cell_level": 15,
        "range": 490,
        "range_init": 980,
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
        "range_init": 980,
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
        self.__shutdown_event = stop_trigger
        self._mapping_mananger = mapping_manager
        self.__route_join_thread: Thread = Thread(name='system', target=self.__route_join)
        self.__route_join_thread.daemon = True
        self.__route_join_thread.start()

    def __route_join(self):
        logger.info("Starting Route join Thread - safemode")
        while not self.__shutdown_event.is_set():
            try:
                routejoin = self._joinqueue.get_nowait()
            except Empty:
                time.sleep(1)
                continue
            except (EOFError, KeyboardInterrupt):
                logger.info("Route join thread noticed shutdown")
                return

            if routejoin is not None:
                logger.info("Try to join routethreads for route {}", routejoin)
                self._mapping_mananger.routemanager_join(routejoin)

    def set_queue(self, item):
        self._joinqueue.put(item)


class MappingManagerManager(SyncManager):
    pass


class MappingManager:
    def __init__(self, db_wrapper: DbWrapper, args, data_manager, configmode: bool = False):
        self.__db_wrapper: DbWrapper = db_wrapper
        self.__args = args
        self.__configmode: bool = configmode
        self.__data_manager = data_manager

        self._devicemappings: Optional[dict] = None
        self._areas: Optional[dict] = None
        self._routemanagers: Optional[Dict[str, dict]] = None
        self._auths: Optional[dict] = None
        self._monlists: Optional[dict] = None
        self.__shutdown_event: Event = Event()
        self.join_routes_queue = JoinQueue(self.__shutdown_event, self)
        self.__raw_json: Optional[dict] = None
        self.__mappings_mutex: Lock = Lock()
        self._known_woorker: dict = {}

        self.update(full_lock=True)

        self.__devicesettings_setter_queue: Queue = Queue()
        self.__devicesettings_setter_consumer_thread: Thread = Thread(name='system',
                                                                      target=self.__devicesettings_setter_consumer, )
        self.__devicesettings_setter_consumer_thread.daemon = True
        self.__devicesettings_setter_consumer_thread.start()

    def shutdown(self):
        logger.fatal("MappingManager exiting")

    def get_auths(self) -> Optional[dict]:
        return self._auths

    def get_devicemappings_of(self, device_name: str) -> Optional[dict]:
        return self._devicemappings.get(device_name, None)

    def get_devicesettings_of(self, device_name: str) -> Optional[dict]:
        return self._devicemappings.get(device_name, None).get('settings', None)

    def __devicesettings_setter_consumer(self):
        logger.info("Starting Devicesettings consumer Thread")
        while not self.__shutdown_event.is_set():
            try:
                set_settings = self.__devicesettings_setter_queue.get_nowait()
            except Empty:
                time.sleep(0.2)
                continue
            except (EOFError, KeyboardInterrupt):
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
                         ' Using empty list instead.', areaname)
            return []
        if listname is not None and int(listname) in self._monlists:
            return self._monlists[int(listname)]
        elif listname is None:
            return []
        else:
            logger.warning("IV list '{}' has been used in area '{}' but does not exist. Using empty IV list instead.",
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

    def get_routemanager_name_from_device(self, device_name: str) -> Optional[str]:
        routemanagers = self.get_all_routemanager_names()
        for routemanager in routemanagers:
            workers = self.routemanager_get_registered_workers(routemanager)
            if device_name in workers:
                return routemanager
        return None

    def device_set_disabled(self, device_name: str, routemanager: str = None) -> bool:
        if routemanager is None:
            routemanager = self.get_routemanager_name_from_device(device_name)
            if routemanager is None:
                logger.info('Device {} is not registered so it cannot be paused', device_name)
                return False
        if routemanager is None:
            return False
        return True

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

    def routemanager_redo_stop(self, routemanager_name: str, worker_name: str, lat: float,
                               lon: float) -> bool:
        routemanager = self.__fetch_routemanager(routemanager_name)
        return routemanager.redo_stop(worker_name, lat, lon) if routemanager is not None else False

    def routemanager_get_registered_workers(self, routemanager_name: str) -> Optional[Set[str]]:
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

    def routemanager_get_calc_type(self, routemanager_name: str) -> bool:
        routemanager = self.__fetch_routemanager(routemanager_name)
        return routemanager.get_calc_type() if routemanager is not None else None

    def routemanager_get_mode(self, routemanager_name: str) -> WorkerType:
        routemanager = self.__fetch_routemanager(routemanager_name)
        return routemanager.get_mode() if routemanager is not None else WorkerType.UNDEFINED.value

    def routemanager_get_name(self, routemanager_name: str) -> Optional[str]:
        routemanager = self.__fetch_routemanager(routemanager_name)
        return routemanager.name if routemanager is not None else None

    def routemanager_get_encounter_ids_left(self, routemanager_name: str) -> Optional[List[int]]:
        routemanager = self.__fetch_routemanager(routemanager_name)
        if routemanager is not None and isinstance(routemanager, RouteManagerIV.RouteManagerIV):
            return routemanager.get_encounter_ids_left()
        else:
            return None

    def routemanager_get_current_route(self, routemanager_name: str) -> Optional[Tuple[List[Location],
                                                                                       Dict[str, List[Location]]]]:
        routemanager = self.__fetch_routemanager(routemanager_name)
        return routemanager.get_current_route() if routemanager is not None else None

    def routemanager_get_current_prioroute(self, routemanager_name: str) -> Optional[List[Location]]:
        routemanager = self.__fetch_routemanager(routemanager_name)
        return routemanager.get_current_prioroute() if routemanager is not None else None

    def routemanager_get_settings(self, routemanager_name: str) -> Optional[dict]:
        routemanager = self.__fetch_routemanager(routemanager_name)
        return routemanager.get_settings() if routemanager is not None else None

    def routemanager_set_worker_sleeping(self, routemanager_name: str, worker_name: str,
                                         sleep_duration: float):
        routemanager = self.__fetch_routemanager(routemanager_name)
        routemanager.set_worker_sleeping(worker_name, sleep_duration)

    def set_worker_startposition(self, routemanager_name: str, worker_name: str,
                                 lat: float, lon: float):
        routemanager = self.__fetch_routemanager(routemanager_name)
        routemanager.set_worker_startposition(worker_name, lat, lon)

    def routemanager_get_position_type(self, routemanager_name: str, worker_name: str) -> Optional[str]:
        routemanager = self.__fetch_routemanager(routemanager_name)
        return routemanager.get_position_type(worker_name) if routemanager is not None else None

    def routemanager_get_max_radius(self, routemanager_name: str):
        routemanager = self.__fetch_routemanager(routemanager_name)
        return routemanager.get_max_radius() if routemanager is not None else None

    def routemanager_recalcualte(self, routemanager_name):
        successful = False
        try:
            routemanager = self.__fetch_routemanager(routemanager_name)
            if not routemanager:
                return False
            active = False
            if routemanager._check_routepools_thread:
                active = True
                successful = True
            else:
                routemanager._start_routemanager()
                active = False
                successful = True
            args = (routemanager._max_radius, routemanager._max_coords_within_radius)
            kwargs = {
                'num_procs': 0,
                'active': active
            }
            recalc_thread = Thread(name=routemanager.name,
                                   target=routemanager.recalc_route_adhoc,
                                   args=args,
                                   kwargs=kwargs)
            recalc_thread.start()
        except Exception:
            logger.opt(exception=True).error('Unable to start recalculation')
        return successful

    def __inherit_device_settings(self, devicesettings, poolsettings):
        inheritsettings = {}
        for pool_setting in poolsettings:
            inheritsettings[pool_setting] = poolsettings[pool_setting]
        for device_setting in devicesettings:
            inheritsettings[device_setting] = devicesettings[device_setting]
        return inheritsettings

    def __get_latest_routemanagers(self) -> Optional[Dict[str, dict]]:
        global mode_mapping
        areas: Optional[Dict[str, dict]] = {}

        if self.__configmode:
            return areas

        raw_areas = self.__data_manager.get_root_resource('area')

        thread_pool = ThreadPool(processes=4)

        areas_procs = {}
        for area_id, area_true in raw_areas.items():
            area = area_true.get_resource()
            if area["geofence_included"] is None:
                raise RuntimeError("Cannot work without geofence_included")

            try:
                geofence_included = self.__data_manager.get_resource('geofence', identifier=area["geofence_included"])
            except Exception:
                raise RuntimeError("geofence_included for area '{}' is specified but does not exist ('{}').".format(
                                   area["name"], geofence_included))

            geofence_excluded_raw_path = area.get("geofence_excluded", None)
            try:
                if geofence_excluded_raw_path is not None:
                    geofence_excluded = self.__data_manager.get_resource('geofence',
                                                                         identifier=geofence_excluded_raw_path)
                else:
                    geofence_excluded = None
            except Exception:
                raise RuntimeError(
                    "geofence_excluded for area '{}' is specified but file does not exist ('{}').".format(
                        area["name"], geofence_excluded_raw_path
                    )
                )

            area_dict = {"mode": area_true.area_type,
                         "geofence_included": geofence_included,
                         "geofence_excluded": geofence_excluded,
                         "routecalc": area["routecalc"],
                         "name": area['name']}
            # also build a routemanager for each area...

            # grab coords
            # first check if init is false, if so, grab the coords from DB
            geofence_helper = GeofenceHelper(geofence_included, geofence_excluded)
            mode = area_true.area_type
            # build routemanagers

            # map iv list to ids
            if area.get('settings', None) is not None and 'mon_ids_iv' in area['settings']:
                # replace list name
                area['settings']['mon_ids_iv_raw'] = \
                    self.get_monlist(area['settings'].get('mon_ids_iv', None), area.get("name", "unknown"))
            route_resource = self.__data_manager.get_resource('routecalc', identifier=area["routecalc"])

            calc_type: str = area.get("route_calc_algorithm", "route")
            route_manager = RouteManagerFactory.get_routemanager(self.__db_wrapper, self.__data_manager,
                                                                 area_id, None,
                                                                 mode_mapping.get(mode, {}).get("range", 0),
                                                                 mode_mapping.get(mode, {}).get("max_count",
                                                                                                99999999),
                                                                 geofence_included,
                                                                 path_to_exclude_geofence=geofence_excluded,
                                                                 mode=mode,
                                                                 settings=area.get("settings", None),
                                                                 init=area.get("init", False),
                                                                 name=area.get("name", "unknown"),
                                                                 level=area.get("level", False),
                                                                 coords_spawns_known=area.get(
                                                                     "coords_spawns_known", False),
                                                                 routefile=route_resource,
                                                                 calctype=calc_type,
                                                                 joinqueue=self.join_routes_queue,
                                                                 S2level=mode_mapping.get(mode, {}).get(
                                                                     "s2_cell_level", 30),
                                                                 include_event_id=area.get(
                                                                     "settings", {}).get("include_event_id", None)
                                                                 )
            logger.info("Initializing area {}", area["name"])
            if mode not in ("iv_mitm", "idle") and calc_type != "routefree":
                coords = self.__fetch_coords(mode, geofence_helper,
                                             coords_spawns_known=area.get("coords_spawns_known", False),
                                             init=area.get("init", False),
                                             range_init=mode_mapping.get(mode, {}).get("range_init", 630),
                                             including_stops=area.get("including_stops", False),
                                             include_event_id=area.get("settings", {}).get("include_event_id", None))

                route_manager.add_coords_list(coords)
                max_radius = mode_mapping[mode]["range"]
                max_count_in_radius = mode_mapping[mode]["max_count"]
                if not area.get("init", False):

                    proc = thread_pool.apply_async(route_manager.initial_calculation,
                                                   args=(max_radius, max_count_in_radius,
                                                         0, False))
                    areas_procs[area_id] = proc
                else:
                    logger.info("Init mode enabled. Going row-based for {}", area.get("name", "unknown"))
                    # we are in init, let's write the init route to file to make it visible in madmin
                    calc_coords = []
                    if area["routecalc"] is not None:
                        for loc in coords:
                            calc_coord = '%s,%s' % (str(loc.lat), str(loc.lng))
                            calc_coords.append(calc_coord)
                        route_resource['routefile'] = calc_coords
                        route_resource.save()
                    # gotta feed the route to routemanager... TODO: without recalc...
                    proc = thread_pool.apply_async(route_manager.recalc_route, args=(1, 99999999,
                                                                                     0, False))
                    areas_procs[area_id] = proc

            area_dict["routemanager"] = route_manager
            areas[area_id] = area_dict

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

        raw_devices = self.__data_manager.get_root_resource('device')
        raw_walkers = self.__data_manager.get_root_resource('walker')
        raw_pools = self.__data_manager.get_root_resource('devicepool')
        raw_walkerareas = self.__data_manager.get_root_resource('walkerarea')

        if raw_devices is None:
            return devices

        for device_id, device in raw_devices.items():
            device_dict = {}
            device_dict.clear()
            device_dict['device_id'] = device_id
            walker = int(device["walker"])
            device_dict["adb"] = device.get("adbname", None)
            pool = device.get("pool", None)
            settings = device.get("settings", None)
            try:
                device_dict["settings"] = self.__inherit_device_settings(settings,
                                                                         raw_pools[int(pool)].get('settings',
                                                                                                  []))
            except (KeyError, AttributeError, TypeError):
                device_dict["settings"] = device.get("settings", None)

            try:
                workerareas = []
                for walkerarea_id in raw_walkers[walker].get('setup', []):
                    workerareas.append(raw_walkerareas[walkerarea_id].get_resource())
                device_dict["walker"] = workerareas
            except (KeyError, AttributeError):
                device_dict["walker"] = []

            devices[device["origin"]] = device_dict
        return devices

    def __fetch_coords(self, mode: str, geofence_helper: GeofenceHelper, coords_spawns_known: bool = False,
                       init: bool = False, range_init: int = 630, including_stops: bool = False,
                       include_event_id=None) -> List[Location]:
        coords: List[Location] = []
        if not init:
            # grab data from DB depending on mode
            # TODO: move routemanagers to factory
            if mode == "raids_mitm":
                coords = self.__db_wrapper.gyms_from_db(geofence_helper)
                if including_stops:
                    try:
                        stops = self.__db_wrapper.stops_from_db(geofence_helper)
                        if stops:
                            coords.extend(stops)
                    except Exception:
                        pass
            elif mode == "mon_mitm":
                if coords_spawns_known:
                    logger.debug("Reading known Spawnpoints from DB")
                    coords = self.__db_wrapper.get_detected_spawns(geofence_helper, include_event_id)
                else:
                    logger.debug("Reading unknown Spawnpoints from DB")
                    coords = self.__db_wrapper.get_undetected_spawns(geofence_helper, include_event_id)
            elif mode == "pokestops":
                coords = self.__db_wrapper.stops_from_db(geofence_helper)
            else:
                logger.error("Mode not implemented yet: {}", mode)
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
        raw_auths = self.__data_manager.get_root_resource('auth')
        if raw_auths is None or len(raw_auths) == 0:
            return None

        auths = {}
        for auth_id, auth in raw_auths.items():
            auths[auth["username"]] = auth["password"]
        return auths

    def __get_latest_areas(self) -> dict:
        areas = {}
        raw_areas = self.__data_manager.get_root_resource('area')

        if raw_areas is None:
            return areas

        for area_id, area in raw_areas.items():
            area_dict = {}
            area_dict['routecalc'] = area.get('routecalc', None)
            area_dict['mode'] = area.area_type
            area_dict['geofence_included'] = area.get(
                'geofence_included', None)
            area_dict['geofence_excluded'] = area.get(
                'geofence_excluded', None)
            area_dict['init'] = area.get('init', False)
            area_dict['name'] = area['name']
            areas[area_id] = area_dict
        return areas

    def __get_latest_monlists(self) -> dict:
        monlist = {}
        monivs = self.__data_manager.get_root_resource('monivlist')

        if monivs is None:
            return monlist

        for moniv_id, elem in monivs.items():
            monlist[moniv_id] = elem.get('mon_ids_iv', None)
        return monlist

    def update(self, full_lock=False):
        """
        Updates the internal mappings and routemanagers
        :return:
        """
        if not full_lock:
            self._monlists = self.__get_latest_monlists()
            areas_tmp = self.__get_latest_areas()
            devicemappings_tmp = self.__get_latest_devicemappings()
            routemanagers_tmp = self.__get_latest_routemanagers()
            auths_tmp = self.__get_latest_auths()

            for area in self._routemanagers:
                logger.info("Stopping all routemanagers and join threads")
                self._routemanagers[area]['routemanager'].stop_routemanager(joinwithqueue=False)
                self._routemanagers[area]['routemanager'].join_threads()

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

            logger.debug("Acquiring lock to update mappings")
            with self.__mappings_mutex:
                self._areas = areas_tmp
                self._devicemappings = devicemappings_tmp
                self._routemanagers = routemanagers_tmp
                self._auths = auths_tmp

        else:
            logger.debug("Acquiring lock to update mappings,full")
            with self.__mappings_mutex:
                self._monlists = self.__get_latest_monlists()
                self._routemanagers = self.__get_latest_routemanagers()
                self._areas = self.__get_latest_areas()
                self._devicemappings = self.__get_latest_devicemappings()
                self._auths = self.__get_latest_auths()

        logger.info("Mappings have been updated")

    def get_all_devices(self):
        devices = []
        devices_raw = self.__data_manager.get_root_resource('device')
        for device_id, device in devices_raw.items():
            devices.append(device['origin'])
        return devices
