import asyncio
import copy
from asyncio import Task, QueueEmpty
from multiprocessing import Event
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.helper.GymHelper import GymHelper
from mapadroid.db.helper.PokestopHelper import PokestopHelper
from mapadroid.db.helper.SettingsAuthHelper import SettingsAuthHelper
from mapadroid.db.helper.SettingsDeviceHelper import SettingsDeviceHelper
from mapadroid.db.helper.SettingsDevicepoolHelper import \
    SettingsDevicepoolHelper
from mapadroid.db.helper.SettingsGeofenceHelper import SettingsGeofenceHelper
from mapadroid.db.helper.SettingsMonivlistHelper import SettingsMonivlistHelper
from mapadroid.db.helper.SettingsPogoauthHelper import SettingsPogoauthHelper
from mapadroid.db.helper.SettingsRoutecalcHelper import SettingsRoutecalcHelper
from mapadroid.db.helper.SettingsWalkerHelper import SettingsWalkerHelper
from mapadroid.db.helper.SettingsWalkerToWalkerareaHelper import \
    SettingsWalkerToWalkerareaHelper
from mapadroid.db.helper.SettingsWalkerareaHelper import \
    SettingsWalkerareaHelper
from mapadroid.db.helper.TrsSpawnHelper import TrsSpawnHelper
from mapadroid.db.model import (SettingsArea, SettingsAuth, SettingsDevice,
                                SettingsDevicepool, SettingsGeofence,
                                SettingsPogoauth, SettingsRoutecalc,
                                SettingsWalker, SettingsWalkerarea,
                                SettingsWalkerToWalkerarea, TrsSpawn)
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.mapping_manager.MappingManagerDevicemappingKey import MappingManagerDevicemappingKey
from mapadroid.route.RouteManagerBase import RouteManagerBase
from mapadroid.route.RouteManagerFactory import RouteManagerFactory
from mapadroid.route.RouteManagerIV import RouteManagerIV
from mapadroid.utils.collections import Location
from mapadroid.utils.language import get_mon_ids
from mapadroid.utils.logging import LoggerEnums, get_logger
from mapadroid.utils.madGlobals import ScreenshotType
from mapadroid.utils.s2Helper import S2Helper
from mapadroid.worker.WorkerType import WorkerType

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


class DeviceMappingsEntry:
    def __init__(self):
        self.device_settings: SettingsDevice = None
        self.ptc_logins: List[SettingsPogoauth] = []
        self.pool_settings: SettingsDevicepool = None
        self.walker_areas: List[SettingsWalkerarea] = []
        # TODO: Ensure those values are being set properly from whereever...
        self.last_location: Location = Location(0.0, 0.0)
        self.last_known_mode: WorkerType = WorkerType.UNDEFINED
        self.account_index: int = 0
        self.account_rotation_started: bool = False
        self.walker_area_index: int = -1
        self.finished: bool = False
        self.job_active: bool = False
        self.last_location_time: Optional[int] = None
        self.last_cleanup_time: Optional[int] = None
        self.last_action_time: Optional[int] = None
        self.last_questclear_time: Optional[int] = None


class AreaEntry:
    def __init__(self):
        self.settings: SettingsArea = None
        self.routecalc: SettingsRoutecalc = None
        self.geofence_included: int = None
        self.geofence_excluded: int = None
        self.init: bool = False


class JoinQueue(object):
    def __init__(self, stop_trigger, mapping_manager):
        self._joinqueue = None
        self.__shutdown_event = stop_trigger
        self._mapping_mananger = mapping_manager

    async def start(self) -> None:
        self._joinqueue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()
        loop.create_task(self.__route_join())

    async def __route_join(self):
        logger.info("Starting Route join Thread - safemode")
        while not self.__shutdown_event.is_set():
            try:
                routejoin = self._joinqueue.get_nowait()
            except QueueEmpty:
                await asyncio.sleep(1)
                continue
            except (EOFError, KeyboardInterrupt):
                logger.info("Route join thread noticed shutdown")
                return

            if routejoin is not None:
                logger.info("Try to join routethreads for route {}", routejoin)
                await self._mapping_mananger.routemanager_join(routejoin)

    async def set_queue(self, item):
        await self._joinqueue.put(item)


class MappingManager:
    def __init__(self, db_wrapper: DbWrapper, args, configmode: bool = False):
        self.__jobstatus: Dict = {}
        self.__db_wrapper: DbWrapper = db_wrapper
        self.__args = args
        self.__configmode: bool = configmode

        self._devicemappings: Optional[Dict[str, DeviceMappingsEntry]] = None
        self._geofence_helpers: Optional[Dict[int, GeofenceHelper]] = None
        self._areas: Optional[Dict[int, AreaEntry]] = None
        self._routemanagers: Optional[Dict[int, RouteManagerBase]] = None
        self._auths: Optional[Dict[str, str]] = None
        self.__areamons: Optional[Dict[int, List[int]]] = {}
        self._monlists: Optional[Dict[int, List[int]]] = None
        self.__shutdown_event: Event = Event()
        self.join_routes_queue = JoinQueue(self.__shutdown_event, self)

        # TODO: Move to init or call __init__ differently...
        self.__paused_devices: List[int] = []
        self.__devicesettings_setter_queue = None
        self.__mappings_mutex = None
        self.__devicesettings_setter_consumer_task: Optional[Task] = None

    async def setup(self):
        self.__devicesettings_setter_queue: asyncio.Queue = asyncio.Queue()
        self.__mappings_mutex: asyncio.Lock = asyncio.Lock()
        await self.join_routes_queue.start()

        loop = asyncio.get_event_loop()
        # TODO: Restore...
        self.__devicesettings_setter_consumer_task = loop.create_task(self.__devicesettings_setter_consumer())

        await self.update(full_lock=True)

    def shutdown(self):
        logger.info("MappingManager exiting")

    async def get_auths(self) -> Optional[Dict[str, str]]:
        return self._auths

    def set_device_state(self, device_id: int, active: int) -> None:
        if active == 1:
            try:
                self.__paused_devices.remove(device_id)
            except ValueError:
                pass
        else:
            if device_id not in self.__paused_devices:
                self.__paused_devices.append(device_id)

    async def is_device_active(self, device_id: int) -> bool:
        return device_id not in self.__paused_devices

    def get_devicemappings_of_sync(self, device_name: str) -> Optional[DeviceMappingsEntry]:
        # Async method since we may move the logic to a different host
        return self._devicemappings.get(device_name, None)

    async def get_devicemappings_of(self, device_name: str) -> Optional[DeviceMappingsEntry]:
        # Async method since we may move the logic to a different host
        return self._devicemappings.get(device_name, None)

    async def get_devicesettings_of(self, device_name: str) -> Optional[Tuple[SettingsDevice, SettingsDevicepool]]:
        devicemapping_entry: Optional[DeviceMappingsEntry] = self._devicemappings.get(device_name, None)
        if not devicemapping_entry:
            return None
        else:
            return devicemapping_entry.device_settings, devicemapping_entry.pool_settings

    # TODO: Move all devicesettings/mappings functionality/handling to dedicated class
    async def __devicesettings_setter_consumer(self):
        logger.info("Starting Devicesettings consumer Thread")
        while not self.__shutdown_event.is_set():
            try:
                set_settings = self.__devicesettings_setter_queue.get_nowait()
            except QueueEmpty:
                await asyncio.sleep(0.2)
                continue
            except (EOFError, KeyboardInterrupt):
                logger.info("Devicesettings setter thread noticed shutdown")
                return

            if set_settings is not None:
                device_name, key, value = set_settings
                async with self.__mappings_mutex:
                    await self.__set_devicesetting(device_name, key, value)

    async def __set_devicesetting(self, device_name: str, key: MappingManagerDevicemappingKey, value: Any) -> None:
        devicemapping_entry: Optional[DeviceMappingsEntry] = self._devicemappings.get(device_name, None)
        if not devicemapping_entry:
            return
        if key == MappingManagerDevicemappingKey.JOB_ACTIVE:
            devicemapping_entry.job_active = value
        elif key == MappingManagerDevicemappingKey.WALKER_AREA_INDEX:
            devicemapping_entry.walker_area_index = value
        elif key == MappingManagerDevicemappingKey.FINISHED:
            devicemapping_entry.finished = value
        elif key == MappingManagerDevicemappingKey.LAST_LOCATION_TIME:
            devicemapping_entry.last_location_time = value
        elif key == MappingManagerDevicemappingKey.LAST_CLEANUP_TIME:
            devicemapping_entry.last_cleanup_time = value
        elif key == MappingManagerDevicemappingKey.LAST_LOCATION:
            devicemapping_entry.last_location = value
        elif key == MappingManagerDevicemappingKey.ACCOUNT_INDEX:
            devicemapping_entry.account_index = value
        elif key == MappingManagerDevicemappingKey.LAST_MODE:
            devicemapping_entry.last_known_mode = value
        elif key == MappingManagerDevicemappingKey.LAST_ACTION_TIME:
            devicemapping_entry.last_action_time = value
        elif key == MappingManagerDevicemappingKey.ACCOUNT_ROTATION_STARTED:
            devicemapping_entry.account_rotation_started = value
        elif key == MappingManagerDevicemappingKey.LAST_QUESTCLEAR_TIME:
            devicemapping_entry.last_questclear_time = value
        else:
            # TODO: Maybe also set DB stuff? async with self.__db_wrapper as session, session:
            pass

    async def get_devicesetting_value_of_device(self, device_name: str, key: MappingManagerDevicemappingKey):
        devicemapping_entry: Optional[DeviceMappingsEntry] = self._devicemappings.get(device_name, None)
        if not devicemapping_entry:
            return
        if key == MappingManagerDevicemappingKey.JOB_ACTIVE:
            return devicemapping_entry.job_active
        elif key == MappingManagerDevicemappingKey.WALKER_AREA_INDEX:
            return devicemapping_entry.walker_area_index
        elif key == MappingManagerDevicemappingKey.FINISHED:
            return devicemapping_entry.finished
        elif key == MappingManagerDevicemappingKey.LAST_LOCATION_TIME:
            return devicemapping_entry.last_location_time
        elif key == MappingManagerDevicemappingKey.LAST_CLEANUP_TIME:
            return devicemapping_entry.last_cleanup_time
        elif key == MappingManagerDevicemappingKey.LAST_LOCATION:
            return devicemapping_entry.last_location
        elif key == MappingManagerDevicemappingKey.ACCOUNT_INDEX:
            return devicemapping_entry.account_index
        elif key == MappingManagerDevicemappingKey.LAST_MODE:
            return devicemapping_entry.last_known_mode
        elif key == MappingManagerDevicemappingKey.LAST_ACTION_TIME:
            return devicemapping_entry.last_action_time
        elif key == MappingManagerDevicemappingKey.ACCOUNT_ROTATION_STARTED:
            return devicemapping_entry.account_rotation_started
        elif key == MappingManagerDevicemappingKey.LAST_QUESTCLEAR_TIME:
            return devicemapping_entry.last_questclear_time
        # DB stuff
        elif key == MappingManagerDevicemappingKey.ENHANCED_MODE_QUEST:
            return devicemapping_entry.pool_settings.enhanced_mode_quest if devicemapping_entry.pool_settings and devicemapping_entry.pool_settings.enhanced_mode_quest else devicemapping_entry.device_settings.enhanced_mode_quest
        elif key == MappingManagerDevicemappingKey.SCREENSHOT_Y_OFFSET:
            return devicemapping_entry.pool_settings.screenshot_y_offset if devicemapping_entry.pool_settings and devicemapping_entry.pool_settings.screenshot_y_offset else devicemapping_entry.device_settings.screenshot_y_offset
        elif key == MappingManagerDevicemappingKey.SCREENSHOT_X_OFFSET:
            return devicemapping_entry.pool_settings.screenshot_x_offset if devicemapping_entry.pool_settings and devicemapping_entry.pool_settings.screenshot_x_offset else devicemapping_entry.device_settings.screenshot_x_offset
        elif key == MappingManagerDevicemappingKey.LOGINTYPE:
            return devicemapping_entry.device_settings.logintype
        elif key == MappingManagerDevicemappingKey.GGL_LOGIN_MAIL:
            return devicemapping_entry.device_settings.ggl_login_mail
        elif key == MappingManagerDevicemappingKey.STARTCOORDS_OF_WALKER:
            return devicemapping_entry.pool_settings.startcoords_of_walker if devicemapping_entry.pool_settings and devicemapping_entry.pool_settings.startcoords_of_walker else devicemapping_entry.device_settings.startcoords_of_walker
        elif key == MappingManagerDevicemappingKey.POST_TURN_SCREEN_ON_DELAY:
            return devicemapping_entry.pool_settings.post_turn_screen_on_delay if devicemapping_entry.pool_settings and devicemapping_entry.pool_settings.post_turn_screen_on_delay else devicemapping_entry.device_settings.post_turn_screen_on_delay
        elif key == MappingManagerDevicemappingKey.POST_SCREENSHOT_DELAY:
            return devicemapping_entry.pool_settings.post_screenshot_delay if devicemapping_entry.pool_settings and devicemapping_entry.pool_settings.post_screenshot_delay else devicemapping_entry.device_settings.post_screenshot_delay
        elif key == MappingManagerDevicemappingKey.POST_WALK_DELAY:
            return devicemapping_entry.pool_settings.post_walk_delay if devicemapping_entry.pool_settings and devicemapping_entry.pool_settings.post_walk_delay else devicemapping_entry.device_settings.post_walk_delay
        elif key == MappingManagerDevicemappingKey.POST_TELEPORT_DELAY:
            return devicemapping_entry.pool_settings.post_teleport_delay if devicemapping_entry.pool_settings and devicemapping_entry.pool_settings.post_teleport_delay else devicemapping_entry.device_settings.post_teleport_delay
        elif key == MappingManagerDevicemappingKey.WALK_AFTER_TELEPORT_DISTANCE:
            return devicemapping_entry.pool_settings.walk_after_teleport_distance if devicemapping_entry.pool_settings and devicemapping_entry.pool_settings.walk_after_teleport_distance else devicemapping_entry.device_settings.walk_after_teleport_distance
        elif key == MappingManagerDevicemappingKey.COOLDOWN_SLEEP:
            return devicemapping_entry.pool_settings.cool_down_sleep if devicemapping_entry.pool_settings and devicemapping_entry.pool_settings.cool_down_sleep else devicemapping_entry.device_settings.cool_down_sleep
        elif key == MappingManagerDevicemappingKey.POST_POGO_START_DELAY:
            return devicemapping_entry.pool_settings.post_pogo_start_delay if devicemapping_entry.pool_settings and devicemapping_entry.pool_settings.post_pogo_start_delay else devicemapping_entry.device_settings.post_pogo_start_delay
        elif key == MappingManagerDevicemappingKey.RESTART_POGO:
            return devicemapping_entry.pool_settings.restart_pogo if devicemapping_entry.pool_settings and devicemapping_entry.pool_settings.restart_pogo else devicemapping_entry.device_settings.restart_pogo
        elif key == MappingManagerDevicemappingKey.INVENTORY_CLEAR_ROUNDS:
            return devicemapping_entry.pool_settings.inventory_clear_rounds if devicemapping_entry.pool_settings and devicemapping_entry.pool_settings.inventory_clear_rounds else devicemapping_entry.device_settings.inventory_clear_rounds
        elif key == MappingManagerDevicemappingKey.MITM_WAIT_TIMEOUT:
            return devicemapping_entry.pool_settings.mitm_wait_timeout if devicemapping_entry.pool_settings and devicemapping_entry.pool_settings.mitm_wait_timeout else devicemapping_entry.device_settings.mitm_wait_timeout
        elif key == MappingManagerDevicemappingKey.VPS_DELAY:
            return devicemapping_entry.pool_settings.vps_delay if devicemapping_entry.pool_settings and devicemapping_entry.pool_settings.vps_delay else devicemapping_entry.device_settings.vps_delay
        elif key == MappingManagerDevicemappingKey.REBOOT:
            return devicemapping_entry.pool_settings.reboot if devicemapping_entry.pool_settings and devicemapping_entry.pool_settings.reboot else devicemapping_entry.device_settings.reboot
        elif key == MappingManagerDevicemappingKey.REBOOT_THRESH:
            return devicemapping_entry.pool_settings.reboot_thresh if devicemapping_entry.pool_settings and devicemapping_entry.pool_settings.reboot_thresh else devicemapping_entry.device_settings.reboot_thresh
        elif key == MappingManagerDevicemappingKey.RESTART_THRESH:
            return devicemapping_entry.pool_settings.restart_thresh if devicemapping_entry.pool_settings and devicemapping_entry.pool_settings.restart_thresh else devicemapping_entry.device_settings.restart_thresh
        elif key == MappingManagerDevicemappingKey.SCREENSHOT_TYPE:
            try:
                return ScreenshotType(
                    devicemapping_entry.pool_settings.screenshot_type if devicemapping_entry.pool_settings and devicemapping_entry.pool_settings.screenshot_type else devicemapping_entry.device_settings.screenshot_type)
            except ValueError:
                return ScreenshotType.JPEG
        elif key == MappingManagerDevicemappingKey.SCREENSHOT_QUALITY:
            quality: Optional[
                int] = devicemapping_entry.pool_settings.screenshot_quality if devicemapping_entry.pool_settings and devicemapping_entry.pool_settings.screenshot_quality else devicemapping_entry.device_settings.screenshot_quality
            return quality if quality else 80
        elif key == MappingManagerDevicemappingKey.INJECTION_THRESH_REBOOT:
            return devicemapping_entry.pool_settings.injection_thresh_reboot if devicemapping_entry.pool_settings and devicemapping_entry.pool_settings.injection_thresh_reboot else devicemapping_entry.device_settings.injection_thresh_reboot
        elif key == MappingManagerDevicemappingKey.SCREENDETECTION:
            return devicemapping_entry.pool_settings.screendetection if devicemapping_entry.pool_settings and devicemapping_entry.pool_settings.screendetection else devicemapping_entry.device_settings.screendetection
        elif key == MappingManagerDevicemappingKey.ENHANCED_MODE_QUEST_SAFE_ITEMS:
            return devicemapping_entry.pool_settings.enhanced_mode_quest_safe_items if devicemapping_entry.pool_settings and devicemapping_entry.pool_settings.enhanced_mode_quest_safe_items else devicemapping_entry.device_settings.enhanced_mode_quest_safe_items
        elif key == MappingManagerDevicemappingKey.CLEAR_GAME_DATA:
            return devicemapping_entry.device_settings.clear_game_data
        # Extra keys to e.g. retrieve PTC accounts
        elif key == MappingManagerDevicemappingKey.PTC_LOGIN:
            return devicemapping_entry.ptc_logins
        elif key == MappingManagerDevicemappingKey.ROTATION_WAITTIME:
            return devicemapping_entry.device_settings.rotation_waittime
        elif key == MappingManagerDevicemappingKey.ACCOUNT_ROTATION:
            return devicemapping_entry.device_settings.account_rotation
        elif key == MappingManagerDevicemappingKey.ROTATE_ON_LVL_30:
            return devicemapping_entry.device_settings.rotate_on_lvl_30
        else:
            # TODO: Get all the DB values...
            pass

    async def set_devicesetting_value_of(self, device_name: str, key: MappingManagerDevicemappingKey, value):
        if self._devicemappings.get(device_name, None) is not None:
            await self.__devicesettings_setter_queue.put((device_name, key, value))

    async def get_all_devicemappings(self) -> Optional[Dict[str, DeviceMappingsEntry]]:
        return self._devicemappings

    async def get_areas(self) -> Optional[Dict[int, AreaEntry]]:
        return self._areas

    def get_monlist(self, area_id) -> List[int]:
        try:
            return self.__areamons[area_id]
        except KeyError:
            return []

    async def get_all_routemanager_ids(self) -> List[int]:
        return list(self._routemanagers.keys())

    def __fetch_routemanager(self, routemanager_id: int) -> Optional[RouteManagerBase]:
        routemanager: RouteManagerBase = self._routemanagers.get(routemanager_id, None)
        return routemanager

    async def routemanager_present(self, routemanager_id: int) -> bool:
        return routemanager_id in self._routemanagers.keys()

    async def routemanager_get_next_location(self, routemanager_id: int, origin: str) -> Optional[Location]:
        routemanager = self.__fetch_routemanager(routemanager_id)
        return await routemanager.get_next_location(origin) if routemanager is not None else None

    async def routemanager_join(self, routemanager_id: int):
        routemanager = self.__fetch_routemanager(routemanager_id)
        if routemanager is not None:
            # TODO... asnycio
            await routemanager.join_threads()

    async def get_routemanager_id_where_device_is_registered(self, device_name: str) -> Optional[int]:
        routemanagers = await self.get_all_routemanager_ids()
        for routemanager in routemanagers:
            workers = await self.routemanager_get_registered_workers(routemanager)
            if device_name in workers:
                return routemanager
        return None

    # def device_set_disabled(self, device_name: str) -> bool:
    #    routemanager = self.get_routemanager_id_where_device_is_registered(device_name)
    #    if routemanager is None:
    #        logger.info('Device {} is not registered so it cannot be paused', device_name)
    #        return False

    #        return True

    async def register_worker_to_routemanager(self, routemanager_id: int, worker_name: str) -> bool:
        routemanager = self.__fetch_routemanager(routemanager_id)
        return routemanager.register_worker(worker_name) if routemanager is not None else False

    async def unregister_worker_from_routemanager(self, routemanager_id: int, worker_name: str):
        routemanager = self.__fetch_routemanager(routemanager_id)
        return await routemanager.unregister_worker(worker_name) if routemanager is not None else None

    async def routemanager_add_coords_to_be_removed(self, routemanager_id: int, lat: float, lon: float):
        routemanager = self.__fetch_routemanager(routemanager_id)
        if routemanager is not None:
            routemanager.add_coord_to_be_removed(lat, lon)

    async def routemanager_get_route_stats(self, routemanager_id: int, origin: str) -> Optional[Tuple[int, int]]:
        routemanager = self.__fetch_routemanager(routemanager_id)
        return routemanager.get_route_status(origin) if routemanager is not None else None

    async def routemanager_get_rounds(self, routemanager_id: int, worker_name: str) -> Optional[int]:
        routemanager = self.__fetch_routemanager(routemanager_id)
        return routemanager.get_rounds(worker_name) if routemanager is not None else None

    async def routemanager_redo_stop(self, routemanager_id: int, worker_name: str, lat: float,
                                     lon: float) -> bool:
        routemanager = self.__fetch_routemanager(routemanager_id)
        return routemanager.redo_stop(worker_name, lat, lon) if routemanager is not None else False

    async def routemanager_get_registered_workers(self, routemanager_id: int) -> Optional[Set[str]]:
        routemanager = self.__fetch_routemanager(routemanager_id)
        return routemanager.get_registered_workers() if routemanager is not None else None

    async def routemanager_get_ids_iv(self, routemanager_id: int) -> Optional[List[int]]:
        routemanager = self.__fetch_routemanager(routemanager_id)
        return routemanager.get_ids_iv() if routemanager is not None else None

    async def routemanager_get_geofence_helper(self, routemanager_id: int) -> Optional[GeofenceHelper]:
        routemanager = self.__fetch_routemanager(routemanager_id)
        return routemanager.get_geofence_helper() if routemanager is not None else None

    async def routemanager_get_init(self, routemanager_id: int) -> bool:
        routemanager = self.__fetch_routemanager(routemanager_id)
        return routemanager.get_init() if routemanager is not None else False

    async def routemanager_get_level(self, routemanager_id: int) -> bool:
        routemanager = self.__fetch_routemanager(routemanager_id)
        return routemanager.get_level_mode() if routemanager is not None else None

    async def routemanager_get_calc_type(self, routemanager_id: int) -> bool:
        routemanager = self.__fetch_routemanager(routemanager_id)
        return routemanager.get_calc_type() if routemanager is not None else None

    async def routemanager_get_mode(self, routemanager_id: int) -> WorkerType:
        routemanager = self.__fetch_routemanager(routemanager_id)
        return routemanager.get_mode() if routemanager is not None else WorkerType.UNDEFINED.value

    async def routemanager_get_name(self, routemanager_id: int) -> Optional[str]:
        routemanager = self.__fetch_routemanager(routemanager_id)
        return routemanager.name if routemanager is not None else None

    async def routemanager_get_encounter_ids_left(self, routemanager_id: int) -> Optional[List[int]]:
        routemanager = self.__fetch_routemanager(routemanager_id)
        if routemanager is not None and isinstance(routemanager, RouteManagerIV):
            return routemanager.get_encounter_ids_left()
        else:
            return None

    async def routemanager_get_current_route(self, routemanager_id: int) -> Optional[Tuple[List[Location],
                                                                                           Dict[
                                                                                               str, List[Location]]]]:
        routemanager = self.__fetch_routemanager(routemanager_id)
        return routemanager.get_current_route() if routemanager is not None else None

    async def routemanager_get_current_prioroute(self, routemanager_id: int) -> Optional[List[Location]]:
        routemanager = self.__fetch_routemanager(routemanager_id)
        return routemanager.get_current_prioroute() if routemanager is not None else None

    async def routemanager_get_settings(self, routemanager_id: int) -> Optional[SettingsArea]:
        routemanager = self.__fetch_routemanager(routemanager_id)
        return routemanager.get_settings() if routemanager is not None else None

    async def routemanager_set_worker_sleeping(self, routemanager_id: int, worker_name: str,
                                               sleep_duration: float):
        routemanager = self.__fetch_routemanager(routemanager_id)
        routemanager.set_worker_sleeping(worker_name, sleep_duration)

    async def set_worker_startposition(self, routemanager_id: int, worker_name: str,
                                       lat: float, lon: float):
        logger.debug("Fetching routemanager")
        routemanager = self.__fetch_routemanager(routemanager_id)
        logger.info("Setting routemanager's startposition")
        routemanager.set_worker_startposition(worker_name, lat, lon)

    async def routemanager_get_position_type(self, routemanager_id: int, worker_name: str) -> Optional[str]:
        routemanager = self.__fetch_routemanager(routemanager_id)
        return routemanager.get_position_type(worker_name) if routemanager is not None else None

    async def routemanager_get_max_radius(self, routemanager_id: int):
        routemanager = self.__fetch_routemanager(routemanager_id)
        return routemanager.get_max_radius() if routemanager is not None else None

    async def routemanager_recalcualte(self, routemanager_id: int):
        successful = False
        try:
            routemanager = self.__fetch_routemanager(routemanager_id)
            if not routemanager:
                return False
            active = False
            if routemanager._check_routepools_thread:
                active = True
                successful = True
            else:
                await routemanager.start_routemanager()
                active = False
                successful = True
            args = (routemanager._max_radius, routemanager._max_coords_within_radius)
            kwargs = {
                'num_procs': 0,
                'active': active
            }
            loop = asyncio.get_running_loop()
            loop.create_task(coro=routemanager.recalc_route_adhoc(*args, **kwargs))
        except Exception:
            logger.opt(exception=True).error('Unable to start recalculation')
        return successful

    async def __get_latest_geofence_helpers(self, session: AsyncSession) -> Dict[int, GeofenceHelper]:
        geofences: Dict[int, SettingsGeofence] = await SettingsGeofenceHelper.get_all_mapped(session,
                                                                                             self.__db_wrapper.get_instance_id())
        geofence_helpers: Dict[int, GeofenceHelper] = {}
        for geofence_id, geofence in geofences.items():
            geofence_helper = GeofenceHelper(geofence, None, geofence.name)
            geofence_helpers[geofence_id] = geofence_helper
        return geofence_helpers

    async def get_geofence_helper(self, geofence_id: int):
        pass

    def __inherit_device_settings(self, devicesettings, poolsettings):
        inheritsettings = {}
        for pool_setting in poolsettings:
            inheritsettings[pool_setting] = poolsettings[pool_setting]
        for device_setting in devicesettings:
            inheritsettings[device_setting] = devicesettings[device_setting]
        return inheritsettings

    async def __get_latest_routemanagers(self, session: AsyncSession) -> Dict[int, RouteManagerBase]:
        # TODO: Use a factory for the iterations...
        global mode_mapping
        areas: Dict[int, SettingsArea] = {}

        if self.__configmode:
            return areas
        areas = await self.__db_wrapper.get_all_areas(session)
        # TODO: use amount of CPUs, use process pool?
        routemanagers: Dict[int, RouteManagerBase] = {}
        areas_procs: Dict[int, Task] = {}
        loop = asyncio.get_running_loop()
        for area_id, area in areas.items():
            if area.geofence_included is None:
                raise RuntimeError("Cannot work without geofence_included")

            try:
                geofence_included: Optional[SettingsGeofence] = await SettingsGeofenceHelper \
                    .get(session, self.__db_wrapper.get_instance_id(), area.geofence_included)
            except Exception:
                raise RuntimeError("geofence_included for area '{}' is specified but does not exist ('{}').".format(
                    area.name, area.geofence_included))

            geofence_excluded: Optional[SettingsGeofence] = None
            if area.mode in ("iv_mitm", "mon_mitm", 'pokestops', 'raids_mitm'):
                try:
                    if area.geofence_excluded is not None:
                        geofence_excluded = await SettingsGeofenceHelper \
                            .get(session, self.__db_wrapper.get_instance_id(), int(area.geofence_excluded))
                except Exception:
                    raise RuntimeError(
                        "geofence_excluded for area '{}' is specified but file does not exist ('{}').".format(
                            area.name, area.geofence_excluded
                        )
                    )
            # also build a routemanager for each area...

            # grab coords
            # first check if init is false, if so, grab the coords from DB
            geofence_helper = GeofenceHelper(geofence_included, geofence_excluded)
            # build routemanagers

            # TODO: Fill with all settings...
            area_settings: Dict[str, Any] = {}

            # map iv list to ids
            if area.mode in ("iv_mitm", "mon_mitm", "raids_mitm") and area.monlist_id:
                # replace list name
                area_settings['mon_ids_iv_raw'] = self.get_monlist(area_id)
            init_area: bool = False
            if area.mode in ("mon_mitm", "raids_mitm", "pokestop") and area.init:
                init_area: bool = area.init
            spawns_known: bool = area.coords_spawns_known if area.mode == "mon_mitm" else True
            routecalc: Optional[SettingsRoutecalc] = await SettingsRoutecalcHelper \
                .get(session, area.routecalc)

            calc_type: str = area.route_calc_algorithm if area.mode == "pokestop" else "route"
            including_stops: bool = area.including_stops if area.mode == "raids_mitm" else False
            level_mode: bool = area.level if area.mode == "pokestop" else False
            # TODO: Refactor most of the code in here moving it to the factory
            # TODO: Use use_s2 ?
            route_manager = RouteManagerFactory.get_routemanager(db_wrapper=self.__db_wrapper,
                                                                 area=area, coords=None,
                                                                 max_radius=mode_mapping.get(area.mode,
                                                                                             {}).get("range", 0),
                                                                 max_coords_within_radius=
                                                                 mode_mapping.get(area.mode, {}).get("max_count",
                                                                                                     99999999),
                                                                 geofence_helper=geofence_helper,
                                                                 routecalc=routecalc,
                                                                 joinqueue=self.join_routes_queue,
                                                                 s2_level=mode_mapping.get(area.mode, {}).get(
                                                                     "s2_cell_level", 30),
                                                                 mon_ids_iv=self.get_monlist(area_id)
                                                                 )
            logger.info("Initializing area {}", area.name)
            if area.mode not in ("iv_mitm", "idle") and calc_type != "routefree":
                include_event_id = area.include_event_id if area.mode == "mon_mitm" else None
                coords = await self.__fetch_coords(session, area.mode, geofence_helper,
                                                   coords_spawns_known=spawns_known,
                                                   init=init_area,
                                                   range_init=mode_mapping.get(area.mode, {}).get("range_init",
                                                                                                  630),
                                                   including_stops=including_stops,
                                                   include_event_id=include_event_id)

                route_manager.add_coords_list(coords)
                max_radius = mode_mapping[area.mode]["range"]
                max_count_in_radius = mode_mapping[area.mode]["max_count"]
                task: Optional[Task] = None
                if not getattr(area, "init", False):
                    # TODO: proper usage in asnycio loop
                    task = loop.create_task(route_manager.initial_calculation(max_radius, max_count_in_radius, 0,
                                                                              False))
                else:
                    logger.info("Init mode enabled. Going row-based for {}", area.name)
                    # we are in init, let's write the init route to file to make it visible in madmin
                    # async with session.begin_nested() as nested:
                    #     calc_coords = []
                    #     if getattr(area, "routecalc", None) is not None:
                    #         for loc in coords:
                    #             calc_coord = '%s,%s' % (str(loc.lat), str(loc.lng))
                    #             calc_coords.append(calc_coord)
                    #         calc_coords = str(calc_coords).replace("\'", "\"")
                    #         routecalc.routefile = str(calc_coords)
                    #         session.add(routecalc)
                    #         await nested.commit()
                    task = loop.create_task(route_manager.recalc_route(1, 99999999, 0, False))
                areas_procs[area_id] = task

            routemanagers[area.area_id] = route_manager
        for area in areas_procs.keys():
            # TODO: Async executors...
            to_be_checked: Task = areas_procs[area]
            await to_be_checked

        return routemanagers

    async def __get_latest_devicemappings(self, session: AsyncSession) -> Dict[str, DeviceMappingsEntry]:
        # returns mapping of devises to areas
        devices: Dict[str, DeviceMappingsEntry] = {}

        devices_of_instance: List[SettingsDevice] = await SettingsDeviceHelper \
            .get_all(session, self.__db_wrapper.get_instance_id())

        if not devices_of_instance:
            return devices

        all_walkers: Dict[int, SettingsWalker] = await SettingsWalkerHelper \
            .get_all_mapped(session, self.__db_wrapper.get_instance_id())
        all_walkerareas: Dict[int, SettingsWalkerarea] = await SettingsWalkerareaHelper \
            .get_all_mapped(session, self.__db_wrapper.get_instance_id())
        all_walkers_to_walkerareas: Dict[int, List[SettingsWalkerToWalkerarea]] = \
            await SettingsWalkerToWalkerareaHelper.get_all_mapped(session, self.__db_wrapper.get_instance_id())
        all_pools: Dict[int, SettingsDevicepool] = await SettingsDevicepoolHelper \
            .get_all_mapped(session, self.__db_wrapper.get_instance_id())

        for device in devices_of_instance:
            device_entry: DeviceMappingsEntry = DeviceMappingsEntry()
            device_entry.device_settings = device

            # Fetch the logins that are assigned to this device...
            accounts_assigned: List[SettingsPogoauth] = await SettingsPogoauthHelper \
                .get_assigned_to_device(session, self.__db_wrapper.get_instance_id(),
                                        device_entry.device_settings.device_id)
            device_entry.ptc_logins.extend(accounts_assigned)

            if device.pool_id is not None:
                device_entry.pool_settings = all_pools.get(device.pool_id, None)

            walker: SettingsWalker = all_walkers.get(device.walker_id, None)
            if walker:
                walkerarea_mappings_of_walker: List[SettingsWalkerToWalkerarea] = all_walkers_to_walkerareas \
                    .get(walker.walker_id, [])
                for walker_to_walkerareas in walkerarea_mappings_of_walker:
                    device_entry.walker_areas.append(all_walkerareas.get(walker_to_walkerareas.walkerarea_id))
            devices[device.name] = device_entry
        return devices

    async def __fetch_coords(self, session: AsyncSession, mode: str, geofence_helper: GeofenceHelper,
                             coords_spawns_known: bool = True,
                             init: bool = False, range_init: int = 630, including_stops: bool = False,
                             include_event_id=None) -> List[Location]:
        coords: List[Location] = []
        if not init:
            # grab data from DB depending on mode
            # TODO: move routemanagers to factory
            if mode == "raids_mitm":
                coords = await GymHelper.get_locations_in_fence(session, geofence_helper)
                if including_stops:
                    try:
                        stops = await PokestopHelper.get_locations_in_fence(session, geofence_helper)
                        if stops:
                            coords.extend(stops)
                    except Exception:
                        pass
            elif mode == "mon_mitm":
                spawns: List[TrsSpawn] = []
                if coords_spawns_known:
                    logger.debug("Reading known Spawnpoints from DB")
                    spawns = await TrsSpawnHelper.get_known_of_area(session, geofence_helper, include_event_id)
                else:
                    logger.debug("Reading unknown Spawnpoints from DB")
                    spawns = await TrsSpawnHelper.get_known_without_despawn_of_area(session, geofence_helper,
                                                                                    include_event_id)
                for spawn in spawns:
                    coords.append(Location(float(spawn.latitude), float(spawn.longitude)))
            elif mode == "pokestops":
                coords = await PokestopHelper.get_locations_in_fence(session, geofence_helper)
            else:
                logger.info("Mode not implemented yet: {}", mode)
                exit(1)
        else:
            # calculate all level N cells (mapping back from mapping above linked to mode)
            coords = S2Helper._generate_locations(range_init, geofence_helper)
        return coords

    async def __get_latest_auths(self, session: AsyncSession) -> Dict[str, str]:
        """
        Reads current self.__raw_json mappings dict and checks if auth directive is present.
        :return: Dict of username : password
        """
        all_auths: List[SettingsAuth] = await SettingsAuthHelper.get_all(session, self.__db_wrapper.get_instance_id())
        if all_auths is None or len(all_auths) == 0:
            return {}

        auths = {}
        for auth in all_auths:
            auths[auth.username] = auth.password
        return auths

    async def __get_latest_areas(self, session: AsyncSession) -> Dict[int, AreaEntry]:
        areas: Dict[int, AreaEntry] = {}

        all_areas: Dict[int, SettingsArea] = await self.__db_wrapper.get_all_areas(session)

        if all_areas is None:
            return areas

        for area_id, area in all_areas.items():
            area_entry: AreaEntry = AreaEntry()
            area_entry.settings = area

            area_entry.routecalc = await SettingsRoutecalcHelper.get(session, area.routecalc)
            # getattr to avoid checking modes individually...
            area_entry.geofence_included = getattr(area, "geofence_included", None)
            area_entry.geofence_excluded = getattr(area, "geofence_excluded", None)
            area_entry.init = getattr(area, "init", None)

            areas[area_id] = area_entry
        return areas

    async def __get_latest_monlists(self, session: AsyncSession) -> Dict[int, List[int]]:
        return await SettingsMonivlistHelper.get_mapped_lists(session, self.__db_wrapper.get_instance_id())

    async def __get_latest_areamons(self, areas: Dict[int, AreaEntry]) -> Dict[int, List[int]]:
        """

        Args:
            areas:

        Returns: Dict with area ID (keys) and raw mon ID lists (values)

        """
        areamons: Dict[int, List[int]] = {}
        for area_id, area in areas.items():
            mon_iv_list_id: Optional[int] = getattr(area.settings, "monlist_id", None)
            all_mons: bool = getattr(area.settings, "all_mons", False)

            mon_list = []
            try:
                mon_list = copy.copy(self._monlists[int(mon_iv_list_id)])
            except (KeyError, TypeError):
                if not all_mons:
                    logger.warning(
                        "IV list '{}' has been used in area '{}' but does not exist. Using empty IV list"
                        "instead.", mon_iv_list_id, area.settings.name
                    )
                    areamons[area_id] = mon_list
                    continue
            if all_mons:
                logger.debug("Area {} is configured for all mons", area.settings.name)
                for mon_id in await get_mon_ids():
                    if mon_id in mon_list:
                        continue
                    mon_list.append(int(mon_id))
            areamons[area_id] = mon_list
        return areamons

    async def update(self, full_lock=False):
        """
        Updates the internal mappings and routemanagers
        :return:
        """
        if not full_lock:
            async with self.__db_wrapper as session, session:
                self._monlists = await self.__get_latest_monlists(session)
                areas_tmp = await self.__get_latest_areas(session)
                self.__areamons = await self.__get_latest_areamons(areas_tmp)
                devicemappings_tmp: Dict[str, DeviceMappingsEntry] = await self.__get_latest_devicemappings(session)
                routemanagers_tmp = await self.__get_latest_routemanagers(session)
                geofence_helpers_tmp = await self.__get_latest_geofence_helpers(session)
                auths_tmp = await self.__get_latest_auths(session)

            for area_id, routemanager in self._routemanagers.items():
                logger.info("Stopping all routemanagers and join threads")
                await routemanager.stop_routemanager(joinwithqueue=False)
                await routemanager.join_threads()

            logger.info("Restoring old devicesettings")
            for dev, mapping in self._devicemappings.items():
                devicemappings_tmp[dev].last_location = mapping.last_location
                devicemappings_tmp[dev].last_known_mode = mapping.last_known_mode
                devicemappings_tmp[dev].account_index = mapping.account_index
                devicemappings_tmp[dev].account_rotation_started = mapping.account_rotation_started
            logger.debug("Acquiring lock to update mappings")
            async with self.__mappings_mutex:
                self._areas = areas_tmp
                self._devicemappings = devicemappings_tmp
                self._routemanagers = routemanagers_tmp
                self._auths = auths_tmp
                self._geofence_helpers = geofence_helpers_tmp

        else:
            logger.debug("Acquiring lock to update mappings,full")
            async with self.__mappings_mutex:
                async with self.__db_wrapper as session, session:
                    self._areas = await self.__get_latest_areas(session)
                    self._monlists = await self.__get_latest_monlists(session)
                    self.__areamons = await self.__get_latest_areamons(self._areas)
                    self._routemanagers = await self.__get_latest_routemanagers(session)
                    self._devicemappings = await self.__get_latest_devicemappings(session)
                    self._auths = await self.__get_latest_auths(session)
                    self._geofence_helpers = await self.__get_latest_geofence_helpers(session)

        logger.info("Mappings have been updated")

    async def get_all_devicenames(self) -> List[str]:
        async with self.__db_wrapper as session, session:
            devices = []
            all_devices: List[SettingsDevice] = await SettingsDeviceHelper.get_all(session,
                                                                                   self.__db_wrapper.get_instance_id())
            for device in all_devices:
                devices.append(device.name)
            return devices

    def get_jobstatus(self) -> Dict:
        return self.__jobstatus
