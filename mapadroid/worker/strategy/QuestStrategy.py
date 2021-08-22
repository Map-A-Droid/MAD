import asyncio
import math
import os
import time
from asyncio import Task
from datetime import timedelta
from difflib import SequenceMatcher
from enum import Enum
from typing import Dict, Union, Tuple, Optional, List

import sqlalchemy
from loguru import logger
from s2sphere import CellId
from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.data_handler.MitmMapper import MitmMapper
from mapadroid.data_handler.mitm_data.holder.latest_mitm_data.LatestMitmDataEntry import LatestMitmDataEntry
from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.helper.PokestopHelper import PokestopHelper
from mapadroid.db.helper.TrsQuestHelper import TrsQuestHelper
from mapadroid.db.helper.TrsVisitedHelper import TrsVisitedHelper
from mapadroid.db.model import SettingsAreaPokestop, Pokestop, SettingsWalkerarea
from mapadroid.mapping_manager.MappingManager import MappingManager
from mapadroid.mapping_manager.MappingManagerDevicemappingKey import MappingManagerDevicemappingKey
from mapadroid.ocr.pogoWindows import PogoWindows
from mapadroid.ocr.screenPath import WordToScreenMatching
from mapadroid.utils.DatetimeWrapper import DatetimeWrapper
from mapadroid.utils.ProtoIdentifier import ProtoIdentifier
from mapadroid.utils.collections import ScreenCoordinates, Location
from mapadroid.utils.gamemechanicutil import calculate_cooldown
from mapadroid.utils.geo import get_distance_of_two_points_in_meters
from mapadroid.utils.madConstants import TIMESTAMP_NEVER
from mapadroid.utils.madGlobals import InternalStopWorkerException, WebsocketWorkerTimeoutException, \
    WebsocketWorkerRemovedException, WebsocketWorkerConnectionClosedException, TransportType, FortSearchResultTypes
from mapadroid.utils.s2Helper import S2Helper
from mapadroid.websocket.AbstractCommunicator import AbstractCommunicator
from mapadroid.worker.ReceivedTypeEnum import ReceivedType
from mapadroid.worker.WorkerState import WorkerState
from mapadroid.worker.strategy.AbstractMitmBaseStrategy import AbstractMitmBaseStrategy

# The diff to lat/lng values to consider that the worker is standing on top of the stop
S2_GMO_CELL_LEVEL = 15
RADIUS_FOR_CELLS_CONSIDERED_FOR_STOP_SCAN = 35
DISTANCE_TO_STOP_TO_CONSIDER_ON_TOP = 0.00006


class ClearThreadTasks(Enum):
    IDLE = 0
    BOX = 1
    QUEST = 2


class PositionStopType(Enum):
    GMO_NOT_AVAILABLE = 0,
    GMO_EMPTY = 1,
    GYM = 2,
    VISITED_STOP_IN_LEVEL_MODE_TO_IGNORE = 3,
    STOP_DISABLED = 4,
    STOP_CLOSED = 5,
    STOP_COOLDOWN = 6
    NO_FORT = 7
    SPINNABLE_STOP = 8

    @staticmethod
    def type_contains_stop_at_all(position_stop_type) -> bool:
        return position_stop_type in (PositionStopType.SPINNABLE_STOP,
                                      PositionStopType.VISITED_STOP_IN_LEVEL_MODE_TO_IGNORE,
                                      PositionStopType.STOP_CLOSED, PositionStopType.STOP_COOLDOWN,
                                      PositionStopType.STOP_DISABLED)


class QuestStrategy(AbstractMitmBaseStrategy):
    def __init__(self, area_id: int, communicator: AbstractCommunicator,
                 mapping_manager: MappingManager,
                 db_wrapper: DbWrapper, word_to_screen_matching: WordToScreenMatching,
                 pogo_windows_handler: PogoWindows,
                 walker: SettingsWalkerarea,
                 worker_state: WorkerState,
                 mitm_mapper: MitmMapper):
        super().__init__(area_id=area_id,
                         communicator=communicator, mapping_manager=mapping_manager,
                         db_wrapper=db_wrapper,
                         word_to_screen_matching=word_to_screen_matching,
                         pogo_windows_handler=pogo_windows_handler,
                         walker=walker,
                         worker_state=worker_state,
                         mitm_mapper=mitm_mapper)
        self.clear_inventory_task: Optional[Task] = None
        self.clear_thread_task: ClearThreadTasks = ClearThreadTasks.IDLE

        self._spinnable_data_failcount = 0
        self._always_cleanup: bool = False
        self._rotation_waittime: int = 0
        self._work_mutex = None
        self._enhanced_mode: False = False
        self._ignore_spinned_stops: bool = False
        self._last_time_quest_received: int = TIMESTAMP_NEVER
        # TODO: Move to worker_state?
        self._delay_add: int = 0
        self._stop_process_time = TIMESTAMP_NEVER

    async def _check_for_data_content(self, latest: Dict[Union[int, str], LatestMitmDataEntry],
                                      proto_to_wait_for: ProtoIdentifier,
                                      timestamp: int) -> Tuple[ReceivedType, Optional[object]]:
        type_of_data_found: ReceivedType = ReceivedType.UNDEFINED
        data_found: Optional[object] = None
        # Check if we have clicked a gym or mon...
        if ProtoIdentifier.GYM_INFO.value in latest \
                and latest[ProtoIdentifier.GYM_INFO.value].timestamp_of_data_retrieval \
                and latest[ProtoIdentifier.GYM_INFO.value].timestamp_of_data_retrieval >= timestamp:
            type_of_data_found = ReceivedType.GYM
            return type_of_data_found, data_found
        elif ProtoIdentifier.ENCOUNTER.value in latest \
                and latest[ProtoIdentifier.ENCOUNTER.value].timestamp_of_data_retrieval \
                and latest[ProtoIdentifier.ENCOUNTER.value].timestamp_of_data_retrieval >= timestamp:
            type_of_data_found = ReceivedType.MON
            return type_of_data_found, data_found
        elif proto_to_wait_for.value not in latest:
            logger.debug("No data linked to the requested proto since MAD started.")
            return type_of_data_found, data_found

        # when waiting for stop or spin data, it is enough to make sure
        # our data is newer than the latest of last quest received, last
        # successful bag clear or last successful quest clear. This eliminates
        # the need to add arbitrary timedeltas for possible small delays,
        # which we don't do in other workers either
        if proto_to_wait_for in [ProtoIdentifier.FORT_SEARCH, ProtoIdentifier.FORT_DETAILS]:
            potential_replacements = [
                self._last_time_quest_received,
                await self.get_devicesettings_value(MappingManagerDevicemappingKey.LAST_CLEANUP_TIME, 0),
                await self.get_devicesettings_value(MappingManagerDevicemappingKey.LAST_QUESTCLEAR_TIME, 0)
            ]
            replacement = max(x for x in potential_replacements if isinstance(x, int) or isinstance(x, float))
            logger.debug("timestamp {} being replaced with {} because we're waiting for proto {}",
                         DatetimeWrapper.fromtimestamp(timestamp).strftime('%H:%M:%S'),
                         DatetimeWrapper.fromtimestamp(replacement).strftime('%H:%M:%S'),
                         proto_to_wait_for)
            timestamp = replacement
        # proto has previously been received, let's check the timestamp...
        latest_proto_entry = latest.get(proto_to_wait_for.value, None)
        if not latest_proto_entry:
            logger.debug("No data linked to the requested proto since MAD started.")
            return type_of_data_found, data_found
        timestamp_of_proto = latest_proto_entry.timestamp_of_data_retrieval
        if not timestamp_of_proto or timestamp_of_proto < timestamp:
            logger.debug("latest timestamp of proto {} ({}) is older than {}", proto_to_wait_for,
                         timestamp_of_proto, timestamp)
            # TODO: timeout error instead of data_error_counter? Differentiate timeout vs missing data (the
            # TODO: latter indicates too high speeds for example
            return type_of_data_found, data_found

        # TODO: consider reseting timestamp here since we clearly received SOMETHING
        latest_proto = latest_proto_entry.data
        logger.debug4("Latest data received: {}", latest_proto)
        if latest_proto is None:
            return type_of_data_found, data_found
        logger.debug2("Checking for Quest related data in proto {}", proto_to_wait_for)
        if latest_proto is None:
            logger.debug("No proto data for {} at {} after {}", proto_to_wait_for,
                         timestamp_of_proto, timestamp)
        elif proto_to_wait_for == ProtoIdentifier.FORT_SEARCH:
            quest_type: int = latest_proto.get('challenge_quest', {}) \
                .get('quest', {}) \
                .get('quest_type', False)
            result: int = latest_proto.get("result", 0)
            if result == 1 and len(latest_proto.get('items_awarded', [])) == 0:
                return ReceivedType.FORT_SEARCH_RESULT, FortSearchResultTypes.TIME
            elif result == 1 and quest_type == 0:
                return ReceivedType.FORT_SEARCH_RESULT, FortSearchResultTypes.FULL
            elif result == 1 and len(latest_proto.get('items_awarded', [])) > 0:
                return ReceivedType.FORT_SEARCH_RESULT, FortSearchResultTypes.QUEST
            elif result == 2:
                return ReceivedType.FORT_SEARCH_RESULT, FortSearchResultTypes.OUT_OF_RANGE
            elif result == 3:
                return ReceivedType.FORT_SEARCH_RESULT, FortSearchResultTypes.COOLDOWN
            elif result == 4:
                return ReceivedType.FORT_SEARCH_RESULT, FortSearchResultTypes.INVENTORY
            elif result == 5:
                return ReceivedType.FORT_SEARCH_RESULT, FortSearchResultTypes.LIMIT
        elif proto_to_wait_for == ProtoIdentifier.FORT_DETAILS:
            fort_type: int = latest_proto.get("type", 0)
            data_found = latest_proto
            type_of_data_found = ReceivedType.GYM if fort_type == 0 else ReceivedType.STOP
        elif proto_to_wait_for == ProtoIdentifier.GMO \
                and self._directly_surrounding_gmo_cells_containing_stops_around_current_position(
                        latest_proto.get("cells")):
            data_found = latest_proto
            type_of_data_found = ReceivedType.GMO
        elif proto_to_wait_for == ProtoIdentifier.INVENTORY and 'inventory_delta' in latest_proto and \
                len(latest_proto['inventory_delta']['inventory_items']) > 0:
            type_of_data_found = ReceivedType.CLEAR
            data_found = latest_proto

        return type_of_data_found, data_found

    def similar(self, elem_a, elem_b):
        return SequenceMatcher(None, elem_a, elem_b).ratio()

    async def pre_work_loop(self):
        if self.clear_inventory_task is not None:
            return
        await super().pre_work_loop()
        if not self._work_mutex:
            self._work_mutex = asyncio.Lock()
        # TODO: Move to worker specific start method and stop it accordingly
        loop = asyncio.get_running_loop()
        self.clear_inventory_task: Task = loop.create_task(self._clear_thread())

        if self._worker_state.stop_worker_event.is_set() or not await self._wait_for_injection():
            raise InternalStopWorkerException

        if await self.get_devicesettings_value(MappingManagerDevicemappingKey.ACCOUNT_ROTATION, False) and not \
                await self.get_devicesettings_value(MappingManagerDevicemappingKey.ACCOUNT_ROTATION_STARTED, False):
            # TODO: Double check account_rotation_started, it is only set to True and never to be touched
            #  again apparently
            # switch to first account if first started and rotation is activated
            if not await self._switch_user():
                logger.error('Something happened during account rotation')
                raise InternalStopWorkerException
            else:
                reached_main_menu = await self._check_pogo_main_screen(10, True)
                if not reached_main_menu:
                    if not await self._restart_pogo(mitm_mapper=self._mitm_mapper):
                        # TODO: put in loop, count up for a reboot ;)
                        raise InternalStopWorkerException

                await self.set_devicesettings_value(MappingManagerDevicemappingKey.ACCOUNT_ROTATION_STARTED, True)
            await asyncio.sleep(10)
        else:
            reached_main_menu = await self._check_pogo_main_screen(10, True)
            if not reached_main_menu:
                if not await self._restart_pogo(mitm_mapper=self._mitm_mapper):
                    # TODO: put in loop, count up for a reboot ;)
                    raise InternalStopWorkerException

        if await self._mapping_manager.routemanager_get_init(self._area_id):
            logger.info("Starting Level Mode")
            if await self._mapping_manager.routemanager_get_calc_type(self._area_id) == "routefree":
                logger.info("Sleeping one minute for getting data")
                await asyncio.sleep(60)
        else:
            # initial cleanup old quests
            self.clear_thread_task: ClearThreadTasks = ClearThreadTasks.QUEST

    async def pre_location_update(self):
        await self._update_injection_settings()

    async def move_to_location(self):
        distance, area_settings = await self._get_route_manager_settings_and_distance_to_current_location()
        area_settings: SettingsAreaPokestop = area_settings
        logger.debug("Getting time")
        if (not area_settings.speed or area_settings.speed == 0 or
                (area_settings.max_distance and 0 < area_settings.max_distance < distance)
                or (self._worker_state.last_location.lat == 0.0 and self._worker_state.last_location.lng == 0.0)):
            logger.debug("main: Teleporting...")
            self._worker_state.last_transport_type = TransportType.TELEPORT
            await self._communicator.set_location(
                Location(self._worker_state.current_location.lat, self._worker_state.current_location.lng), 0)
            # the time we will take as a starting point to wait for data...
            cur_time = math.floor(time.time())

            delay_used = await self.get_devicesettings_value(MappingManagerDevicemappingKey.POST_TELEPORT_DELAY, 0)
            speed = 16.67  # Speed can be 60 km/h up to distances of 3km

            if self._worker_state.last_location.lat == 0.0 and self._worker_state.last_location.lng == 0.0:
                logger.info('Starting fresh round - using lower delay')
            else:
                delay_used = calculate_cooldown(distance, speed)
            logger.debug(
                "Need more sleep after Teleport: {} seconds!", int(delay_used))
        else:
            delay_used = distance / (area_settings.speed / 3.6)  # speed is in kmph , delay_used need mps
            logger.info("main: Walking {} m, this will take {} seconds", distance, delay_used)
            cur_time = await self._walk_to_location(area_settings.speed)

            delay_used = await self.get_devicesettings_value(MappingManagerDevicemappingKey.POST_WALK_DELAY, 0)
        walk_distance_post_teleport = await self.get_devicesettings_value(
            MappingManagerDevicemappingKey.WALK_AFTER_TELEPORT_DISTANCE, 0)
        if 0 < walk_distance_post_teleport < distance:
            # TODO: actually use to_walk for distance
            to_walk = await self._walk_after_teleport(walk_distance_post_teleport)
            delay_used -= (to_walk / 3.05) - 1.  # We already waited for a bit because of this walking part
            if delay_used < 0:
                delay_used = 0

        if await self._mapping_manager.routemanager_get_init(self._area_id):
            delay_used = 5

        if await self.get_devicesettings_value(MappingManagerDevicemappingKey.LAST_ACTION_TIME, None) is not None:
            timediff = time.time() - await self.get_devicesettings_value(
                MappingManagerDevicemappingKey.LAST_ACTION_TIME, 0)
            logger.info("Timediff between now and last action time: {}", int(timediff))
            delay_used = delay_used - timediff
        elif await self.get_devicesettings_value(MappingManagerDevicemappingKey.LAST_ACTION_TIME,
                                                 None) is None and not await self._mapping_manager.routemanager_is_levelmode(
            self._area_id):
            logger.info('Starting first time - we wait because of some default pogo delays ...')
            delay_used = 20
        else:
            logger.debug("No last action time found - no calculation")
            delay_used = -1

        if await self.get_devicesettings_value(MappingManagerDevicemappingKey.SCREENDETECTION, True) and \
                await self._word_to_screen_matching.return_memory_account_count() > 1 and delay_used >= self._rotation_waittime \
                and await self.get_devicesettings_value(MappingManagerDevicemappingKey.ACCOUNT_ROTATION,
                                                        False) and not await self._mapping_manager.routemanager_is_levelmode(
            self._area_id):
            # Waiting time to long and more then one account - switch! (not level mode!!)
            logger.info('Could use more then 1 account - switch & no cooldown')
            await self.switch_account()
            delay_used = -1

        if delay_used < 0:
            self._worker_state.current_sleep_time = 0
            logger.info('No need to wait before spinning, continuing...')
        else:
            delay_used = math.floor(delay_used)
            logger.info("Real sleep time: {} seconds: next action {}", delay_used,
                        DatetimeWrapper.now() + timedelta(seconds=delay_used))
            cleanupbox: bool = False
            lastcleanupbox = await self.get_devicesettings_value(MappingManagerDevicemappingKey.LAST_CLEANUP_TIME, None)

            self._worker_state.current_sleep_time = delay_used
            await self.worker_stats()

            if lastcleanupbox is not None:
                if time.time() - lastcleanupbox > 900:
                    # just cleanup if last cleanup time > 15 minutes ago
                    cleanupbox = True
            else:
                cleanupbox = True
            await self._mapping_manager.routemanager_set_worker_sleeping(self._area_id,
                                                                         self._worker_state.origin,
                                                                         delay_used)
            while time.time() <= int(cur_time) + int(delay_used):
                if delay_used > 200 and cleanupbox and not self._enhanced_mode:
                    self.clear_thread_task = ClearThreadTasks.BOX
                cleanupbox = False
                if not await self._mapping_manager.routemanager_present(self._area_id) \
                        or self._worker_state.stop_worker_event.is_set():
                    logger.error("Worker was killed while sleeping")
                    self._worker_state.current_sleep_time = 0
                    raise InternalStopWorkerException
                await asyncio.sleep(1)

        self._worker_state.current_sleep_time = 0
        await self.set_devicesettings_value(MappingManagerDevicemappingKey.LAST_LOCATION,
                                            self._worker_state.current_location)
        self._worker_state.last_location = self._worker_state.current_location
        return cur_time, True

    async def post_move_location_routine(self, timestamp):
        if self._worker_state.stop_worker_event.is_set():
            raise InternalStopWorkerException
        position_type = await self._mapping_manager.routemanager_get_position_type(self._area_id,
                                                                                   self._worker_state.origin)
        if position_type is None:
            logger.warning("Mappings/Routemanagers have changed, stopping worker to be created again")
            raise InternalStopWorkerException

        if await self.get_devicesettings_value(MappingManagerDevicemappingKey.ROTATE_ON_LVL_30, False) \
                and await self._mitm_mapper.get_level(self._worker_state.origin) >= 30 \
                and await self._mapping_manager.routemanager_is_levelmode(self._area_id):
            # switch if player lvl >= 30
            await self.switch_account()

        async with self._work_mutex:
            if not await self._mapping_manager.routemanager_get_init(self._area_id):
                logger.info("Processing Stop / Quest...")

                on_main_menu = await self._check_pogo_main_screen(10, False)
                if not on_main_menu:
                    await self._restart_pogo(mitm_mapper=self._mitm_mapper)

                logger.info('Open Stop')
                self._stop_process_time = math.floor(time.time())
                type_received: ReceivedType = await self._try_to_open_pokestop(timestamp)
                if type_received is not None and type_received == ReceivedType.STOP:
                    await self._handle_stop(self._stop_process_time)

            else:
                logger.debug('Currently in INIT Mode - no Stop processing')
                await asyncio.sleep(5)

    async def worker_specific_setup_start(self):
        if not self._work_mutex:
            self._work_mutex: asyncio.Lock = asyncio.Lock()
        area_settings: Optional[SettingsAreaPokestop] = await self._mapping_manager.routemanager_get_settings(
            self._area_id)
        self._rotation_waittime = await self.get_devicesettings_value(MappingManagerDevicemappingKey.ROTATION_WAITTIME,
                                                                      300)
        self._always_cleanup: bool = False if area_settings.cleanup_every_spin == 0 else True
        self._delay_add = int(await self.get_devicesettings_value(MappingManagerDevicemappingKey.VPS_DELAY, 0))
        self._enhanced_mode = await self.get_devicesettings_value(MappingManagerDevicemappingKey.ENHANCED_MODE_QUEST,
                                                                  False)
        self._ignore_spinned_stops: bool = False if area_settings.ignore_spinned_stops == 0 else True

    async def worker_specific_setup_stop(self):
        if self.clear_inventory_task is not None:
            self.clear_inventory_task.cancel()

    async def _get_trash_positions(self, full_screen=False) -> List[ScreenCoordinates]:
        logger.debug2("_get_trash_positions: Get_trash_position.")
        if not await self._take_screenshot(
                delay_before=await self.get_devicesettings_value(MappingManagerDevicemappingKey.POST_SCREENSHOT_DELAY,
                                                                 1)):
            logger.debug("_get_trash_positions: Failed getting screenshot")
            return []

        if os.path.isdir(await self.get_screenshot_path()):
            logger.error("_get_trash_positions: screenshot.png is not a file/corrupted")
            return []

        logger.debug2("_get_trash_positions: checking screen")
        return await self._pogo_windows_handler.get_trash_click_positions(await self.get_screenshot_path(),
                                                                          full_screen=full_screen)

    async def _check_pogo_button(self):
        logger.debug("checkPogoButton: Trying to find buttons")
        pogo_topmost = await self._communicator.is_pogo_topmost()
        if not pogo_topmost:
            return False
        if not await self._take_screenshot(
                delay_before=await self.get_devicesettings_value(MappingManagerDevicemappingKey.POST_SCREENSHOT_DELAY,
                                                                 1)):
            logger.debug("checkPogoButton: Failed getting screenshot")
            return False
        # TODO: os operation asyncio?
        if os.path.isdir(await self.get_screenshot_path()):
            logger.error("checkPogoButton: screenshot.png is not a file/corrupted")
            return False

        logger.debug("checkPogoButton: checking for buttons")
        # TODO: need to be non-blocking
        found: bool = False
        coordinates: Optional[ScreenCoordinates] = await self._pogo_windows_handler \
            .look_for_button(await self.get_screenshot_path(), 2.20, 3.01)
        if coordinates:
            await self._communicator.click(coordinates.x, coordinates.y)
            await asyncio.sleep(1)
            logger.debug("checkPogoButton: Found button (small)")
        else:
            coordinates: Optional[ScreenCoordinates] = await self._pogo_windows_handler \
                .look_for_button(await self.get_screenshot_path(), 1.05, 2.20)
            if coordinates:
                await self._communicator.click(coordinates.x, coordinates.y)
                await asyncio.sleep(1)
                logger.debug("checkPogoButton: Found button (big)")
                found = True
        logger.debug("checkPogoButton: done")
        return found

    async def _check_pogo_close(self, takescreen=True):
        logger.debug("checkPogoClose: Trying to find closeX")
        if not await self._communicator.is_pogo_topmost():
            return False

        if takescreen:
            if not await self._take_screenshot(delay_before=await self.get_devicesettings_value(
                    MappingManagerDevicemappingKey.POST_SCREENSHOT_DELAY, 1)):
                logger.debug("checkPogoClose: Could not get screenshot")
                return False

        # TODO: Async...
        if os.path.isdir(await self.get_screenshot_path()):
            logger.error("checkPogoClose: screenshot.png is not a file/corrupted")
            return False

        logger.debug("checkPogoClose: checking for CloseX")
        found = await self._pogo_windows_handler.check_close_except_nearby_button(await self.get_screenshot_path(),
                                                                                  self._worker_state.origin)
        if found:
            await self._communicator.click(found[0].x, found[0].y)
            await asyncio.sleep(1)
            logger.debug("checkPogoClose: Found (X) button (except nearby)")
            logger.debug("checkPogoClose: done")
            return True
        logger.debug("checkPogoClose: done")
        return False

    async def _clear_thread(self):
        logger.info('Starting clear Quest Thread')
        vps_delay: int = await self._get_vps_delay()
        while not self._worker_state.stop_worker_event.is_set():
            if self.clear_thread_task == ClearThreadTasks.IDLE:
                await asyncio.sleep(1)
                continue

            async with self._work_mutex:
                try:
                    await asyncio.sleep(1)
                    if self.clear_thread_task == ClearThreadTasks.BOX:
                        logger.info("Clearing box")
                        await self.clear_box(vps_delay)
                        self.clear_thread_task = ClearThreadTasks.IDLE
                    elif self.clear_thread_task == ClearThreadTasks.QUEST and not await self._mapping_manager.routemanager_is_levelmode(
                            self._area_id):
                        logger.info("Clearing quest")
                        await self._clear_quests(vps_delay)
                        self.clear_thread_task = ClearThreadTasks.IDLE
                    await asyncio.sleep(1)
                except (InternalStopWorkerException, WebsocketWorkerRemovedException,
                        WebsocketWorkerTimeoutException, WebsocketWorkerConnectionClosedException):
                    logger.error("Worker removed while clearing quest/box")
                    self._worker_state.stop_worker_event.set()
                    return
                finally:
                    self.clear_thread_task = ClearThreadTasks.IDLE

    async def clear_box(self, delayadd):
        # TODO: these events are odd...
        stop_inventory_clear = asyncio.Event()
        stop_screen_clear = asyncio.Event()
        logger.info('Cleanup Box')
        await self._mapping_manager.routemanager_set_worker_sleeping(self._area_id,
                                                                     self._worker_state.origin,
                                                                     300)
        not_allow = ('Gift', 'Geschenk', 'Glücksei', 'Glucks-Ei', 'Glücks-Ei', 'Lucky Egg', 'CEuf Chance',
                     'Cadeau', 'Appareil photo', 'Wunderbox', 'Mystery Box', 'Boîte Mystère', 'Premium',
                     'Raid', 'Teil',
                     'Élément', 'mystérieux', 'Mysterious', 'Component', 'Mysteriöses', 'Remote', 'Fern',
                     'Fern-Raid-Pass', 'Pass', 'Passe', 'distance', 'Remote Raid', 'Remote Pass',
                     'Remote Raid Pass', 'Battle Pass', 'Premium Battle Pass', 'Premium Battle', 'Sticker',
                     'Premium-Kampf')
        x, y = self._worker_state.resolution_calculator.get_close_main_button_coords()
        await self._communicator.click(int(x), int(y))
        await asyncio.sleep(1 + int(delayadd))
        x, y = self._worker_state.resolution_calculator.get_item_menu_coords()
        await self._communicator.click(int(x), int(y))
        await asyncio.sleep(2 + int(delayadd))
        text_x1, text_x2, _, _ = self._worker_state.resolution_calculator.get_delete_item_text()
        x, y = self._worker_state.resolution_calculator.get_delete_item_coords()
        click_x, click_y = self._worker_state.resolution_calculator.get_click_item_minus()
        delrounds_remaining = int(
            await self.get_devicesettings_value(MappingManagerDevicemappingKey.INVENTORY_CLEAR_ROUNDS, 10))
        first_round = True
        delete_allowed = False
        error_counter = 0
        success_counter = 0

        while not stop_inventory_clear.is_set() and delrounds_remaining > 0:

            if not first_round and not delete_allowed:
                error_counter += 1
                if error_counter > 3:
                    stop_inventory_clear.set()
                    if success_counter == 0:
                        self._clear_box_failcount += 1
                        if self._clear_box_failcount < 3:
                            logger.warning("Failed clearing box {} time(s) in a row, retry later...",
                                           self._clear_box_failcount)
                        else:
                            logger.error("Unable to delete any items 3 times in a row - restart pogo ...")
                            if not await self._restart_pogo(mitm_mapper=self._mitm_mapper):
                                # TODO: put in loop, count up for a reboot ;)
                                raise InternalStopWorkerException
                    continue
                logger.info('Found no item to delete. Scrolling down ({} times)', error_counter)
                await self._communicator.touch_and_hold(int(200), int(600), int(200), int(100))
                await asyncio.sleep(5)

            trashcan_positions: List[ScreenCoordinates] = await self._get_trash_positions()

            if not trashcan_positions:
                logger.warning('Could not find any trashcans - abort')
                return
            logger.info("Found {} trashcans on screen", len(trashcan_positions))
            first_round = False
            delete_allowed = False
            stop_screen_clear.clear()

            trash = 0
            while int(trash) <= len(trashcan_positions) - 1 and not stop_screen_clear.is_set():
                check_y_text_starter = int(trashcan_positions[trash].y)
                check_y_text_ending = int(trashcan_positions[trash].y) \
                                      + self._worker_state.resolution_calculator.get_inventory_text_diff()

                try:
                    item_text = await self._pogo_windows_handler.get_inventory_text(await self.get_screenshot_path(),
                                                                                    self._worker_state.origin, text_x1,
                                                                                    text_x2,
                                                                                    check_y_text_ending,
                                                                                    check_y_text_starter)
                    if item_text is None:
                        logger.warning("Did not get any text in inventory")
                        # TODO: could this be running forever?
                        trash += 1
                        continue
                    logger.debug("Found item {}", item_text)
                    match_one_item: bool = False
                    for text in not_allow:
                        if self.similar(text, item_text) > 0.6:
                            match_one_item = True
                            break
                    if match_one_item:
                        logger.debug('Not allowed to delete item. Skipping: {}', item_text)
                        trash += 1
                    else:
                        logger.info('Going to delete item: {}', item_text)
                        await self._communicator.click(int(trashcan_positions[trash].x),
                                                       int(trashcan_positions[trash].y))
                        await asyncio.sleep(1 + int(delayadd))

                        await self._communicator.click(click_x, click_y)
                        await asyncio.sleep(1)

                        delx, dely = self._worker_state.resolution_calculator.get_confirm_delete_item_coords()
                        cur_time = time.time()
                        await self._communicator.click(int(delx), int(dely))
                        deletion_timeout = 35
                        type_received, proto_entry = await self._wait_for_data(timestamp=cur_time,
                                                                               proto_to_wait_for=ProtoIdentifier.INVENTORY,
                                                                               timeout=deletion_timeout)

                        if type_received != ReceivedType.UNDEFINED:
                            if type_received == ReceivedType.CLEAR:
                                success_counter += 1
                                self._clear_box_failcount = 0
                                await self.set_devicesettings_value(MappingManagerDevicemappingKey.LAST_CLEANUP_TIME,
                                                                    int(time.time()))
                                delrounds_remaining -= 1
                                stop_screen_clear.set()
                                delete_allowed = True
                            else:
                                logger.warning("Did not receive confirmation of deletion of items in time")
                        else:
                            logger.warning('Deletion not confirmed within {}s for item: {}', deletion_timeout,
                                           item_text)
                            stop_screen_clear.set()
                            stop_inventory_clear.set()
                except UnicodeEncodeError:
                    logger.warning('Unable to identify item while ')
                    stop_inventory_clear.set()
                    stop_screen_clear.set()
                    pass

        x, y = self._worker_state.resolution_calculator.get_close_main_button_coords()
        await self._communicator.click(int(x), int(y))
        await asyncio.sleep(1 + int(delayadd))
        return True

    async def _clear_quests(self, delayadd, openmenu=True):
        logger.debug('{_clear_quests} called')
        if openmenu:
            x, y = self._worker_state.resolution_calculator.get_coords_quest_menu()
            await self._communicator.click(int(x), int(y))
            logger.debug("_clear_quests Open menu: {}, {}", int(x), int(y))
            await asyncio.sleep(6 + int(delayadd))

        x, y = self._worker_state.resolution_calculator.get_close_main_button_coords()
        await self._communicator.click(int(x), int(y))
        await asyncio.sleep(1.5)
        logger.debug('{_clear_quests} finished')

    async def switch_account(self):
        if not self._switch_user():
            logger.error('Something happend while account switching :(')
            raise InternalStopWorkerException
        else:
            await asyncio.sleep(10)
            reached_main_menu = await self._check_pogo_main_screen(10, True)
            if not reached_main_menu:
                if not await self._restart_pogo(mitm_mapper=self._mitm_mapper):
                    # TODO: put in loop, count up for a reboot ;)
                    raise InternalStopWorkerException

    async def _update_injection_settings(self):
        injected_settings = {}
        scanmode = "quests"
        injected_settings["scanmode"] = scanmode
        ids_iv: List[int] = []
        self._encounter_ids = {}
        await self._mitm_mapper.update_latest(worker=self._worker_state.origin, key="ids_encountered",
                                              value=self._encounter_ids)
        await self._mitm_mapper.update_latest(worker=self._worker_state.origin, key="ids_iv", value=ids_iv)

        await self._mitm_mapper.update_latest(worker=self._worker_state.origin, key="injected_settings",
                                              value=injected_settings)

    async def _try_to_open_pokestop(self, timestamp: float) -> ReceivedType:
        to = 0
        type_received: ReceivedType = ReceivedType.UNDEFINED
        proto_entry = None
        # let's first check the GMO for the stop we intend to visit and abort if it's disabled, a gym, whatsoever
        stop_type: PositionStopType = await self._current_position_has_spinnable_stop(timestamp)

        recheck_count = 0
        while stop_type in (PositionStopType.GMO_NOT_AVAILABLE, PositionStopType.GMO_EMPTY,
                            PositionStopType.NO_FORT) and not recheck_count > 2:
            recheck_count += 1
            logger.info("Wait for new data to check the stop again ... (attempt {})", recheck_count + 1)
            type_received, proto_entry = await self._wait_for_data(timestamp=time.time(),
                                                                   proto_to_wait_for=ProtoIdentifier.GMO,
                                                                   timeout=20)
            if type_received != ReceivedType.UNDEFINED:
                stop_type = await self._current_position_has_spinnable_stop(timestamp)

        if not PositionStopType.type_contains_stop_at_all(stop_type):
            logger.info("Location {}, {} considered to be ignored in the next round due to failed "
                        "spinnable check",
                        self._worker_state.current_location.lat,
                        self._worker_state.current_location.lng)
            await self._mapping_manager.routemanager_add_coords_to_be_removed(self._area_id,
                                                                              self._worker_state.current_location.lat,
                                                                              self._worker_state.current_location.lng)
            return type_received
        elif stop_type in (PositionStopType.STOP_CLOSED, PositionStopType.STOP_COOLDOWN,
                           PositionStopType.STOP_DISABLED):
            logger.info("Stop at {}, {} is not spinnable at the moment ({})",
                        self._worker_state.current_location.lat,
                        self._worker_state.current_location.lng,
                        stop_type)
            return type_received
        elif stop_type == PositionStopType.VISITED_STOP_IN_LEVEL_MODE_TO_IGNORE:
            logger.info("Stop at {}, {} has been spun before and is to be ignored in the next round.")
            await self._mapping_manager.routemanager_add_coords_to_be_removed(self._area_id,
                                                                              self._worker_state.current_location.lat,
                                                                              self._worker_state.current_location.lng)
            return type_received

        while type_received != ReceivedType.STOP and int(to) < 3:
            self._stop_process_time = math.floor(time.time())
            await self._click_pokestop_at_current_location(self._delay_add)
            await self.set_devicesettings_value(MappingManagerDevicemappingKey.LAST_ACTION_TIME, time.time())
            type_received, proto_entry = await self._wait_for_data(
                timestamp=self._stop_process_time, proto_to_wait_for=ProtoIdentifier.FORT_DETAILS, timeout=15)
            if type_received == ReceivedType.GYM:
                logger.info('Clicked GYM')
                await asyncio.sleep(5)
                x, y = self._worker_state.resolution_calculator.get_close_main_button_coords()
                await self._communicator.click(int(x), int(y))
                await asyncio.sleep(3)
                await self._turn_map(self._delay_add)
                await asyncio.sleep(1)
            elif type_received == ReceivedType.MON:
                await asyncio.sleep(1)
                logger.info('Clicked MON')
                await asyncio.sleep(.5)
                await self._turn_map(self._delay_add)
                await asyncio.sleep(1)
            elif type_received == ReceivedType.UNDEFINED:
                logger.info('Getting timeout - or other unknown error. Trying again')
                if not await self._check_pogo_button():
                    await self._check_pogo_close(takescreen=True)

            to += 1
            if to > 2:
                logger.warning("Giving up on this stop after 3 failures in open_pokestop loop")
        return type_received

    # TODO: handle https://github.com/Furtif/POGOProtos/blob/master/src/POGOProtos/Networking/Responses
    #  /FortSearchResponse.proto#L12
    async def _handle_stop(self, timestamp: float):
        to = 0
        timeout = 35
        type_received: ReceivedType = ReceivedType.UNDEFINED
        data_received = FortSearchResultTypes.UNDEFINED
        async with self._db_wrapper as session, session:
            while data_received != FortSearchResultTypes.QUEST and int(to) < 4:
                logger.info('Spin Stop')
                type_received, data_received = await self._wait_for_data(
                    timestamp=self._stop_process_time, proto_to_wait_for=ProtoIdentifier.FORT_SEARCH, timeout=timeout)

                if (type_received == ReceivedType.FORT_SEARCH_RESULT
                        and data_received == FortSearchResultTypes.INVENTORY):
                    logger.info('Box is full... clear out items!')
                    self.clear_thread_task = ClearThreadTasks.BOX
                    await asyncio.sleep(5)
                    if not await self._mapping_manager.routemanager_redo_stop(self._area_id,
                                                                              self._worker_state.origin,
                                                                              self._worker_state.current_location.lat,
                                                                              self._worker_state.current_location.lng):
                        logger.warning('Cannot process this stop again')
                    break
                elif (type_received == ReceivedType.FORT_SEARCH_RESULT
                      and (data_received == FortSearchResultTypes.QUEST
                           or data_received == FortSearchResultTypes.COOLDOWN
                           or (
                                   data_received == FortSearchResultTypes.FULL and await self._mapping_manager.routemanager_is_levelmode(
                               self._area_id)))):
                    if await self._mapping_manager.routemanager_is_levelmode(self._area_id):
                        logger.info("Saving visitation info...")
                        self._last_time_quest_received = math.floor(time.time())
                        await TrsVisitedHelper.mark_visited(session, self._worker_state.origin,
                                                            self._worker_state.current_location)
                        try:
                            await session.commit()
                        except Exception as e:
                            logger.warning("Failed marking stop as visited: {}", e)
                        # This is leveling mode, it's faster to just ignore spin result and continue ?
                        break

                    if data_received == FortSearchResultTypes.COOLDOWN:
                        logger.info('Stop is on cooldown.. sleeping 10 seconds but probably should just move on')
                        await asyncio.sleep(10)

                        if await TrsQuestHelper.check_stop_has_quest(session, self._worker_state.current_location):
                            logger.info('Quest is done without us noticing. Getting new Quest...')
                        self.clear_thread_task = ClearThreadTasks.QUEST
                        break
                    elif data_received == FortSearchResultTypes.QUEST:
                        logger.info('Received new Quest')
                        self._last_time_quest_received = math.floor(time.time())

                    if not self._enhanced_mode:
                        if not self._always_cleanup:
                            self._clear_quest_counter += 1
                            if self._clear_quest_counter == 3:
                                logger.info('Collected 3 quests - clean them')
                                reached_main_menu = await self._check_pogo_main_screen(10, True)
                                if not reached_main_menu:
                                    if not await self._restart_pogo(mitm_mapper=self._mitm_mapper):
                                        # TODO: put in loop, count up for a reboot ;)
                                        raise InternalStopWorkerException
                                self.clear_thread_task = ClearThreadTasks.QUEST
                                self._clear_quest_counter = 0
                        else:
                            logger.info('Getting new quest - clean it')
                            reached_main_menu = await self._check_pogo_main_screen(10, True)
                            if not reached_main_menu:
                                if not await self._restart_pogo(mitm_mapper=self._mitm_mapper):
                                    # TODO: put in loop, count up for a reboot ;)
                                    raise InternalStopWorkerException
                            self.clear_thread_task = ClearThreadTasks.QUEST
                        break

                elif (type_received == ReceivedType.FORT_SEARCH_RESULT
                      and (data_received == FortSearchResultTypes.TIME
                           or data_received == FortSearchResultTypes.OUT_OF_RANGE)):
                    logger.warning('Softban - return to main screen and open again...')
                    on_main_menu = await self._check_pogo_main_screen(10, False)
                    if not on_main_menu:
                        await self._restart_pogo(mitm_mapper=self._mitm_mapper)
                    self._stop_process_time = math.floor(time.time())
                    if await self._try_to_open_pokestop(self._stop_process_time) == ReceivedType.UNDEFINED:
                        return
                elif (type_received == ReceivedType.FORT_SEARCH_RESULT
                      and data_received == FortSearchResultTypes.FULL):
                    logger.warning(
                        "Failed getting quest but got items - quest box is probably full. Starting cleanup "
                        "routine.")
                    reached_main_menu = await self._check_pogo_main_screen(10, True)
                    if not reached_main_menu:
                        if not await self._restart_pogo(mitm_mapper=self._mitm_mapper):
                            # TODO: put in loop, count up for a reboot ;)
                            raise InternalStopWorkerException
                    self.clear_thread_task = ClearThreadTasks.QUEST
                    self._clear_quest_counter = 0
                    break
                else:
                    if data_received == ReceivedType.MON:
                        logger.info("Got MON data after opening stop. This does not make sense - just retry...")
                    else:
                        logger.info("Brief speed lock or we already spun it, trying again")
                    if to > 2 and await TrsQuestHelper.check_stop_has_quest(session,
                                                                            self._worker_state.current_location):
                        logger.info('Quest is done without us noticing. Getting new Quest...')
                        if not self._enhanced_mode:
                            self.clear_thread_task = ClearThreadTasks.QUEST
                        break
                    elif to > 2 and await self._mapping_manager.routemanager_is_levelmode(
                            self._area_id) and await self._mitm_mapper.get_poke_stop_visits(
                        self._worker_state.origin) > 6800:
                        logger.warning("Might have hit a spin limit for worker! We have spun: {} stops",
                                       await self._mitm_mapper.get_poke_stop_visits(self._worker_state.origin))

                    await self._turn_map(self._delay_add)
                    await asyncio.sleep(1)
                    self._stop_process_time = math.floor(time.time())
                    if await self._try_to_open_pokestop(self._stop_process_time) == ReceivedType.UNDEFINED:
                        return
                    to += 1
                    if to > 3:
                        logger.warning("giving up spinning after 4 tries in handle_stop loop")

        await self.set_devicesettings_value(MappingManagerDevicemappingKey.LAST_ACTION_TIME, time.time())

    async def _current_position_has_spinnable_stop(self, timestamp: float) -> PositionStopType:
        type_received, data_received = await self._wait_for_data(timestamp=timestamp,
                                                                 proto_to_wait_for=ProtoIdentifier.GMO)
        if type_received != ReceivedType.GMO or data_received is None:
            await self._spinnable_data_failure()
            return PositionStopType.GMO_NOT_AVAILABLE
        latest_proto = data_received
        gmo_cells: list = latest_proto.get("cells", None)

        if not gmo_cells:
            logger.warning("Can't spin stop - no map info in GMO!")
            await self._spinnable_data_failure()
            return PositionStopType.GMO_EMPTY

        cells_with_stops = self._directly_surrounding_gmo_cells_containing_stops_around_current_position(gmo_cells)
        async with self._db_wrapper as session, session:
            for cell in cells_with_stops:
                forts: list = cell.get("forts", None)
                if not forts:
                    continue

                for fort in forts:
                    latitude: float = fort.get("latitude", 0.0)
                    longitude: float = fort.get("longitude", 0.0)
                    if latitude == 0.0 or longitude == 0.0:
                        continue
                    elif (abs(self._worker_state.current_location.lat - latitude) <= DISTANCE_TO_STOP_TO_CONSIDER_ON_TOP
                          and abs(
                                self._worker_state.current_location.lng - longitude) <= DISTANCE_TO_STOP_TO_CONSIDER_ON_TOP):
                        # We are basically on top of a stop
                        logger.info("Found stop/gym at current location!")
                    else:
                        logger.debug2(
                            "Found stop nearby but not next to us to be spinned. Current lat, lng: {}, {}."
                            "Stop at {}, {}",
                            self._worker_state.current_location.lat,
                            self._worker_state.current_location.lng,
                            latitude, longitude)
                        continue

                    fort_type: int = fort.get("type", 0)
                    if fort_type == 0:
                        await PokestopHelper.delete(session, Location(latitude, longitude))
                        logger.warning("Tried to open a stop but found a gym instead!")
                        self._spinnable_data_failcount = 0
                        try:
                            await session.commit()
                        except Exception as e:
                            logger.warning("Failed deleting pokestop: {}", e)
                        return PositionStopType.GYM

                    visited: bool = fort.get("visited", False)
                    if await self._mapping_manager.routemanager_is_levelmode(
                            self._area_id) and self._ignore_spinned_stops and visited:
                        logger.info("Level mode: Stop already visited - skipping it")
                        await TrsVisitedHelper.mark_visited(session, self._worker_state.origin,
                                                            Location(latitude, longitude))
                        self._spinnable_data_failcount = 0
                        try:
                            await session.commit()
                        except Exception as e:
                            logger.warning("Failed mark pokestop visited: {}", e)
                        return PositionStopType.VISITED_STOP_IN_LEVEL_MODE_TO_IGNORE

                    enabled: bool = fort.get("enabled", True)
                    if not enabled:
                        logger.info("Can't spin the stop - it is disabled")
                        return PositionStopType.STOP_DISABLED
                    closed: bool = fort.get("closed", False)
                    if closed:
                        logger.info("Can't spin the stop - it is closed")
                        return PositionStopType.STOP_CLOSED

                    cooldown: int = fort.get("cooldown_complete_ms", 0)
                    if not cooldown == 0:
                        logger.info("Can't spin the stop - it has cooldown")
                        return PositionStopType.STOP_COOLDOWN
                    self._spinnable_data_failcount = 0
                    return PositionStopType.SPINNABLE_STOP

            # by now we should've found the stop in the GMO
            logger.warning("Unable to confirm the current location ({}) yielding a spinnable stop "
                           "- likely not standing exactly on top ...",
                           self._worker_state.current_location)
            await self._check_if_stop_was_nearby_and_update_location(session, gmo_cells)
            await self._spinnable_data_failure()
            try:
                await session.commit()
            except Exception as e:
                logger.exception(e)
                await session.rollback()
            return PositionStopType.NO_FORT

    async def _click_pokestop_at_current_location(self, delayadd):
        logger.debug('{_open_gym} called')
        await asyncio.sleep(.5)
        x, y = self._worker_state.resolution_calculator.get_gym_click_coords()
        await self._communicator.click(int(x), int(y))
        await asyncio.sleep(.5 + int(delayadd))
        logger.debug('{_open_gym} finished')

    async def _turn_map(self, delayadd):
        logger.debug('{_turn_map} called')
        logger.info('Turning map')
        x1, x2, y = self._worker_state.resolution_calculator.get_gym_spin_coords()
        await self._communicator.swipe(int(x1), int(y), int(x2), int(y))
        await asyncio.sleep(int(delayadd))
        logger.debug('{_turn_map} called')

    async def _spinnable_data_failure(self):
        if self._spinnable_data_failcount > 9:
            self._spinnable_data_failcount = 0
            logger.warning("Worker failed spinning stop with GMO/data issues 10+ times - restart pogo")
            if not await self._restart_pogo(mitm_mapper=self._mitm_mapper):
                # TODO: put in loop, count up for a reboot ;)
                raise InternalStopWorkerException
        else:
            self._spinnable_data_failcount += 1

    def _directly_surrounding_gmo_cells_containing_stops_around_current_position(self, gmo_cells) -> List:
        """
        Returns a list of cells containing forts
        Args:
            gmo_cells:

        Returns:
            List of cells that actually contain forts around the current position
        """
        cells_with_forts = []
        if not gmo_cells:
            logger.debug("No GMO cells passed for surrounding cell check")
            return cells_with_forts
        # 35m radius around current location (thus cells that may be touched by that radius hopefully get included)
        s2cells_valid_around_location: List[CellId] = \
            S2Helper.get_s2cells_from_circle(self._worker_state.current_location.lat,
                                             self._worker_state.current_location.lng,
                                             RADIUS_FOR_CELLS_CONSIDERED_FOR_STOP_SCAN,
                                             S2_GMO_CELL_LEVEL)
        s2cell_ids_valid: List[str] = [s2cell.id() for s2cell in s2cells_valid_around_location]
        for cell in gmo_cells:
            # each cell contains an array of forts, check each cell for a fort with our current location (maybe +-
            # very very little jitter) and check its properties
            if cell["id"] not in s2cell_ids_valid:
                continue
            forts: list = cell.get("forts", None)
            if forts:
                cells_with_forts.append(cell)

        if not cells_with_forts:
            logger.debug2("GMO cells around current position ({}) do not contain stops ",
                          self._worker_state.current_location)
        return cells_with_forts

    async def _check_if_stop_was_nearby_and_update_location(self, session: AsyncSession, gmo_cells):
        logger.info("Checking stops around current location ({}) for deleted stops.",
                    self._worker_state.current_location)

        stops: Dict[str, Pokestop] = await PokestopHelper.get_nearby(session, self._worker_state.current_location)
        logger.debug("Checking if GMO contains location changes or DB has stops that are already deleted. In DB: "
                     "{}. GMO cells: {}", str(stops), gmo_cells)
        # stops may contain multiple stops now. We can check each ID (key of dict) with the IDs in the GMO.
        # Then cross check against the location. If that differs, we need to update/delete the entries in the DB
        for cell in gmo_cells:
            forts: list = cell.get("forts", None)
            if not forts:
                continue

            for fort in forts:
                latitude: float = fort.get("latitude", None)
                longitude: float = fort.get("longitude", None)
                fort_id: str = fort.get("id", None)
                if not latitude or not longitude or not fort_id:
                    logger.warning("Cannot process fort without id, lat or lon")
                    continue
                stop: Optional[Pokestop] = stops.get(fort_id)
                if stop is None:
                    # new stop we have not seen before, MITM processors should take care of that
                    logger.debug2("Stop not in DB (in range) with ID {} at {}, {}", fort_id, latitude, longitude)
                    continue
                else:
                    stops.pop(fort_id)
                if stop.latitude == latitude and stop.longitude == longitude:
                    # Location of fort has not changed
                    logger.debug2("Fort {} has not moved", fort_id)
                    continue
                else:
                    # now we have a location from DB for the given stop we are currently processing but does not equal
                    # the one we are currently processing, thus SAME fort_id
                    # now update the stop
                    logger.warning("Updating fort {} with previous location {}, {} now placed at {}, {}",
                                   fort_id, stop.latitude, stop.longitude, latitude, longitude)
                    async with self._db_wrapper as fresh_session, fresh_session:
                        await PokestopHelper.update_location(fresh_session, fort_id, Location(latitude, longitude))
                        try:
                            await fresh_session.commit()
                        except sqlalchemy.exc.InternalError as e:
                            logger.warning("Failed updating location of stop")
                            logger.exception(e)
                            await fresh_session.rollback()

        timedelta_to_consider_deletion = timedelta(days=3)
        for fort_id, stop in stops.items():
            # Call delete of stops that have been not been found within 100m range of current position
            stop_location: Location = Location(float(stop.latitude), float(stop.longitude))
            logger.debug("Considering stop {} at {} (last updated {}) for deletion",
                         fort_id, stop_location, stop.last_updated)
            if stop.last_updated and stop.last_updated > DatetimeWrapper.now() - timedelta_to_consider_deletion:
                logger.debug3("Stop considered for deletion was last updated recently, not gonna delete it for"
                              " now.", stop.last_updated)
                continue
            distance_to_location = get_distance_of_two_points_in_meters(float(stop_location.lat),
                                                                        float(stop_location.lng),
                                                                        float(self._worker_state.current_location.lat),
                                                                        float(self._worker_state.current_location.lng))
            logger.debug("Distance to {} at {} (last updated {})",
                         fort_id, stop_location, stop.last_updated)
            if distance_to_location < 100:
                logger.warning(
                    "Deleting stop {} at {} since it could not be found in the GMO but was present in DB and within "
                    "100m of worker ({}m) and was last updated more than 3 days ago ()",
                    fort_id, str(stop_location), distance_to_location, stop.last_updated)
                async with session.begin_nested() as nested_session:
                    await PokestopHelper.delete(session, stop_location)
                    try:
                        nested_session.commit()
                    except sqlalchemy.exc.InternalError as e:
                        logger.warning("Failed deleting stop")
                        logger.exception(e)
                await self._mapping_manager.routemanager_add_coords_to_be_removed(self._area_id,
                                                                                  stop_location.lat,
                                                                                  stop_location.lng)
