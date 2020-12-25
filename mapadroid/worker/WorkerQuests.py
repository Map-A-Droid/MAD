import math
import time
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from enum import Enum
from threading import Event, Thread
from typing import Dict, List, Optional, Tuple, Union

from s2sphere import CellId

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.mitm_receiver.MitmMapper import MitmMapper
from mapadroid.ocr.pogoWindows import PogoWindows
from mapadroid.utils import MappingManager
from mapadroid.utils.collections import Location
from mapadroid.utils.gamemechanicutil import calculate_cooldown
from mapadroid.utils.geo import get_distance_of_two_points_in_meters
from mapadroid.utils.logging import LoggerEnums, get_logger
from mapadroid.utils.madGlobals import (
    InternalStopWorkerException, WebsocketWorkerConnectionClosedException,
    WebsocketWorkerRemovedException, WebsocketWorkerTimeoutException)
from mapadroid.utils.ProtoIdentifier import ProtoIdentifier
from mapadroid.utils.s2Helper import S2Helper
from mapadroid.websocket.AbstractCommunicator import AbstractCommunicator
from mapadroid.worker.MITMBase import LatestReceivedType, MITMBase
from mapadroid.worker.WorkerBase import FortSearchResultTypes

# The diff to lat/lng values to consider that the worker is standing on top of the stop
S2_GMO_CELL_LEVEL = 15
RADIUS_FOR_CELLS_CONSIDERED_FOR_STOP_SCAN = 35
DISTANCE_TO_STOP_TO_CONSIDER_ON_TOP = 0.00006

logger = get_logger(LoggerEnums.worker)


class ClearThreadTasks(Enum):
    IDLE = 0
    BOX = 1
    QUEST = 2


class WorkerQuests(MITMBase):

    def similar(self, elem_a, elem_b):
        return SequenceMatcher(None, elem_a, elem_b).ratio()

    def __init__(self, args, dev_id, origin, last_known_state, communicator: AbstractCommunicator,
                 mapping_manager: MappingManager,
                 area_id: int, routemanager_name: str, db_wrapper: DbWrapper,
                 pogo_window_manager: PogoWindows, walker,
                 mitm_mapper: MitmMapper, event):
        MITMBase.__init__(self, args, dev_id, origin, last_known_state, communicator,
                          mapping_manager=mapping_manager, routemanager_name=routemanager_name,
                          area_id=area_id,
                          db_wrapper=db_wrapper,
                          mitm_mapper=mitm_mapper, pogo_window_manager=pogo_window_manager, walker=walker,
                          event=event)
        self.clear_thread = None
        # 0 => None
        # 1 => clear box
        # 2 => clear quest
        self.clear_thread_task = ClearThreadTasks.IDLE
        self._delay_add = int(self.get_devicesettings_value("vps_delay", 0))
        self._stop_process_time = 0
        self._clear_quest_counter = 0
        self._level_mode = self._mapping_manager.routemanager_get_level(self._routemanager_name)
        self._ignore_spinned_stops = self._mapping_manager.routemanager_get_settings(self._routemanager_name) \
            .get("ignore_spinned_stops", True)
        self._always_cleanup = self._mapping_manager.routemanager_get_settings(self._routemanager_name) \
            .get("cleanup_every_spin", False)

        self._rotation_waittime = self.get_devicesettings_value('rotation_waittime', 300)
        self._latest_quest = 0
        self._clear_box_failcount = 0
        self._spinnable_data_failcount = 0

    def _pre_work_loop(self):
        if self.clear_thread is not None:
            return
        self.clear_thread = Thread(name=self._origin, target=self._clear_thread)
        self.clear_thread.daemon = True
        self.clear_thread.start()

        if not self._wait_for_injection() or self._stop_worker_event.is_set():
            raise InternalStopWorkerException

        if self.get_devicesettings_value('account_rotation', False) and not \
                self.get_devicesettings_value('account_rotation_started', False):
            # switch to first account if first started and rotation is activated
            if not self._switch_user():
                self.logger.error('Something happened during account rotation')
                raise InternalStopWorkerException
            else:
                reached_main_menu = self._check_pogo_main_screen(10, True)
                if not reached_main_menu:
                    if not self._restart_pogo(mitm_mapper=self._mitm_mapper):
                        # TODO: put in loop, count up for a reboot ;)
                        raise InternalStopWorkerException

                self.set_devicesettings_value('account_rotation_started', True)
            time.sleep(10)
        else:
            reached_main_menu = self._check_pogo_main_screen(10, True)
            if not reached_main_menu:
                if not self._restart_pogo(mitm_mapper=self._mitm_mapper):
                    # TODO: put in loop, count up for a reboot ;)
                    raise InternalStopWorkerException

        if self._level_mode:
            self.logger.info("Starting Level Mode")
            if self._mapping_manager.routemanager_get_calc_type(self._routemanager_name) == "routefree":
                self.logger.info("Sleeping one minute for getting data")
                time.sleep(60)
        else:
            # initial cleanup old quests
            if not self._init:
                self.clear_thread_task = ClearThreadTasks.QUEST

    def _health_check(self):
        """
        Not gonna check for main screen here since we will do health checks in post_move_location_routine
        :return:
        """
        pass

    def _pre_location_update(self):
        self._update_injection_settings()

    def _move_to_location(self):
        distance, routemanager_settings = self._get_route_manager_settings_and_distance_to_current_location()

        self.logger.debug("Getting time")
        speed = routemanager_settings.get("speed", 0)
        max_distance = routemanager_settings.get("max_distance", None)
        if (speed == 0 or (max_distance and 0 < max_distance < distance)
                or (self.last_location.lat == 0.0 and self.last_location.lng == 0.0)):
            self.logger.debug("main: Teleporting...")
            self._transporttype = 0
            self._communicator.set_location(
                Location(self.current_location.lat, self.current_location.lng), 0)
            # the time we will take as a starting point to wait for data...
            cur_time = math.floor(time.time())

            delay_used = self.get_devicesettings_value('post_teleport_delay', 0)
            speed = 16.67  # Speed can be 60 km/h up to distances of 3km

            if self.last_location.lat == 0.0 and self.last_location.lng == 0.0:
                self.logger.info('Starting fresh round - using lower delay')
            else:
                delay_used = calculate_cooldown(distance, speed)
            self.logger.debug(
                "Need more sleep after Teleport: {} seconds!", int(delay_used))
        else:
            delay_used = distance / (speed / 3.6)  # speed is in kmph , delay_used need mps
            self.logger.info("main: Walking {} m, this will take {} seconds", distance, delay_used)
            cur_time = self._walk_to_location(speed)

            delay_used = self.get_devicesettings_value('post_walk_delay', 0)
        walk_distance_post_teleport = self.get_devicesettings_value('walk_after_teleport_distance', 0)
        if 0 < walk_distance_post_teleport < distance:
            # TODO: actually use to_walk for distance
            to_walk = self._walk_after_teleport(walk_distance_post_teleport)
            delay_used -= (to_walk / 3.05) - 1.  # We already waited for a bit because of this walking part
            if delay_used < 0:
                delay_used = 0

        if self._init:
            delay_used = 5

        if self.get_devicesettings_value('last_action_time', None) is not None:
            timediff = time.time() - self.get_devicesettings_value('last_action_time', 0)
            self.logger.info("Timediff between now and last action time: {}", int(timediff))
            delay_used = delay_used - timediff
        elif self.get_devicesettings_value('last_action_time', None) is None and not self._level_mode:
            self.logger.info('Starting first time - we wait because of some default pogo delays ...')
            delay_used = 20
        else:
            self.logger.debug("No last action time found - no calculation")
            delay_used = -1

        if self.get_devicesettings_value('screendetection', True) and \
                self._WordToScreenMatching.return_memory_account_count() > 1 and delay_used >= self._rotation_waittime \
                and self.get_devicesettings_value('account_rotation', False) and not self._level_mode:
            # Waiting time to long and more then one account - switch! (not level mode!!)
            self.logger.info('Could use more then 1 account - switch & no cooldown')
            self.switch_account()
            delay_used = -1

        if delay_used < 0:
            self._current_sleep_time = 0
            self.logger.info('No need to wait before spinning, continuing...')
        else:
            delay_used = math.floor(delay_used)
            self.logger.info("Real sleep time: {} seconds: next action {}", delay_used,
                             datetime.now() + timedelta(seconds=delay_used))
            cleanupbox: bool = False
            lastcleanupbox = self.get_devicesettings_value('last_cleanup_time', None)

            self._current_sleep_time = delay_used
            self.worker_stats()

            if lastcleanupbox is not None:
                if time.time() - lastcleanupbox > 900:
                    # just cleanup if last cleanup time > 15 minutes ago
                    cleanupbox = True
            else:
                cleanupbox = True
            self._mapping_manager.routemanager_set_worker_sleeping(self._routemanager_name, self._origin,
                                                                   delay_used)
            while time.time() <= int(cur_time) + int(delay_used):
                if delay_used > 200 and cleanupbox and not self._enhanced_mode:
                    self.clear_thread_task = ClearThreadTasks.BOX
                cleanupbox = False
                if not self._mapping_manager.routemanager_present(self._routemanager_name) \
                        or self._stop_worker_event.is_set():
                    self.logger.error("Worker was killed while sleeping")
                    self._current_sleep_time = 0
                    raise InternalStopWorkerException
                time.sleep(1)

        self._current_sleep_time = 0
        self.set_devicesettings_value("last_location", self.current_location)
        self.last_location = self.current_location
        return cur_time, True

    def switch_account(self):
        if not self._switch_user():
            self.logger.error('Something happend while account switching :(')
            raise InternalStopWorkerException
        else:
            time.sleep(10)
            reached_main_menu = self._check_pogo_main_screen(10, True)
            if not reached_main_menu:
                if not self._restart_pogo(mitm_mapper=self._mitm_mapper):
                    # TODO: put in loop, count up for a reboot ;)
                    raise InternalStopWorkerException

    def _post_move_location_routine(self, timestamp: float):
        if self._stop_worker_event.is_set():
            raise InternalStopWorkerException
        position_type = self._mapping_manager.routemanager_get_position_type(self._routemanager_name,
                                                                             self._origin)
        if position_type is None:
            self.logger.warning("Mappings/Routemanagers have changed, stopping worker to be created again")
            raise InternalStopWorkerException

        if self.get_devicesettings_value('rotate_on_lvl_30', False) and \
                self._mitm_mapper.get_playerlevel(self._origin) >= 30 and self._level_mode:
            # switch if player lvl >= 30
            self.switch_account()

        try:
            self._work_mutex.acquire()
            if not self._mapping_manager.routemanager_get_init(self._routemanager_name):
                self.logger.info("Processing Stop / Quest...")

                on_main_menu = self._check_pogo_main_screen(10, False)
                if not on_main_menu:
                    self._restart_pogo(mitm_mapper=self._mitm_mapper)

                self.logger.info('Open Stop')
                self._stop_process_time = math.floor(time.time())
                type_received: LatestReceivedType = self._try_to_open_pokestop(timestamp)
                if type_received is not None and type_received == LatestReceivedType.STOP:
                    self._handle_stop(self._stop_process_time)

            else:
                self.logger.debug('Currently in INIT Mode - no Stop processing')
                time.sleep(5)
        finally:
            self.logger.debug("Releasing lock")
            self._work_mutex.release()

    def _cleanup(self):
        if self.clear_thread is not None:
            while self.clear_thread.isAlive():
                self.clear_thread.join()
                time.sleep(1)

    def _clear_thread(self):
        self.logger.info('Starting clear Quest Thread')
        while not self._stop_worker_event.is_set():
            if self.clear_thread_task == ClearThreadTasks.IDLE:
                time.sleep(1)
                continue

            try:
                self._work_mutex.acquire()
                time.sleep(1)
                if self.clear_thread_task == ClearThreadTasks.BOX:
                    self.logger.info("Clearing box")
                    self.clear_box(self._delay_add)
                    self.clear_thread_task = ClearThreadTasks.IDLE
                elif self.clear_thread_task == ClearThreadTasks.QUEST and not self._level_mode:
                    self.logger.info("Clearing quest")
                    self._clear_quests(self._delay_add)
                    self.clear_thread_task = ClearThreadTasks.IDLE
                time.sleep(1)
            except (InternalStopWorkerException, WebsocketWorkerRemovedException,
                    WebsocketWorkerTimeoutException, WebsocketWorkerConnectionClosedException):
                self.logger.error("Worker removed while clearing quest/box")
                self._stop_worker_event.set()
                return
            finally:
                self.clear_thread_task = ClearThreadTasks.IDLE
                self._work_mutex.release()

    def clear_box(self, delayadd):
        stop_inventory_clear = Event()
        stop_screen_clear = Event()
        self.logger.info('Cleanup Box')
        self._mapping_manager.routemanager_set_worker_sleeping(self._routemanager_name, self._origin, 300)
        not_allow = ('Gift', 'Geschenk', 'Glücksei', 'Glucks-Ei', 'Glücks-Ei', 'Lucky Egg', 'CEuf Chance',
                     'Cadeau', 'Appareil photo', 'Wunderbox', 'Mystery Box', 'Boîte Mystère', 'Premium',
                     'Raid', 'Teil',
                     'Élément', 'mystérieux', 'Mysterious', 'Component', 'Mysteriöses', 'Remote', 'Fern',
                     'Fern-Raid-Pass', 'Pass', 'Passe', 'distance', 'Remote Raid', 'Remote Pass',
                     'Remote Raid Pass', 'Battle Pass', 'Premium Battle Pass', 'Premium Battle', 'Sticker')
        x, y = self._resocalc.get_close_main_button_coords(self)
        self._communicator.click(int(x), int(y))
        time.sleep(1 + int(delayadd))
        x, y = self._resocalc.get_item_menu_coords(self)
        self._communicator.click(int(x), int(y))
        time.sleep(2 + int(delayadd))
        text_x1, text_x2, _, _ = self._resocalc.get_delete_item_text(self)
        x, y = self._resocalc.get_delete_item_coords(
            self)[0], self._resocalc.get_delete_item_coords(self)[1]
        click_x1, click_x2, click_y = self._resocalc.get_swipe_item_amount(self)
        click_duration = int(self.get_devicesettings_value("inventory_clear_item_amount_tap_duration", 3)) * 1000
        delrounds_remaining = int(self.get_devicesettings_value("inventory_clear_rounds", 10))
        first_round = True
        delete_allowed = False
        error_counter = 0
        success_counter = 0

        while delrounds_remaining > 0 and not stop_inventory_clear.is_set():

            trash = 0
            if not first_round and not delete_allowed:
                error_counter += 1
                if error_counter > 3:
                    stop_inventory_clear.set()
                    if success_counter == 0:
                        self._clear_box_failcount += 1
                        if self._clear_box_failcount < 3:
                            self.logger.warning("Failed clearing box {} time(s) in a row, retry later...",
                                                self._clear_box_failcount)
                        else:
                            self.logger.error("Unable to delete any items 3 times in a row - restart pogo ...")
                            if not self._restart_pogo(mitm_mapper=self._mitm_mapper):
                                # TODO: put in loop, count up for a reboot ;)
                                raise InternalStopWorkerException
                    continue
                self.logger.info('Found no item to delete. Scrolling down ({} times)', error_counter)
                self._communicator.touch_and_hold(int(200), int(600), int(200), int(100))
                time.sleep(5)

            trashcancheck = self._get_trash_positions()

            if trashcancheck is None:
                self.logger.warning('Could not find any trashcans - abort')
                return
            self.logger.info("Found {} trashcans on screen", len(trashcancheck))
            first_round = False
            delete_allowed = False
            stop_screen_clear.clear()

            while int(trash) <= len(trashcancheck) - 1 and not stop_screen_clear.is_set():
                check_y_text_starter = int(trashcancheck[trash].y)
                check_y_text_ending = int(trashcancheck[trash].y) + self._resocalc.get_inventory_text_diff(
                    self)

                try:
                    item_text = self._pogoWindowManager.get_inventory_text(self.get_screenshot_path(),
                                                                           self._origin, text_x1, text_x2,
                                                                           check_y_text_ending,
                                                                           check_y_text_starter)
                    if item_text is None:
                        self.logger.warning("Did not get any text in inventory")
                        # TODO: could this be running forever?
                        trash += 1
                        continue
                    self.logger.debug("Found item {}", item_text)
                    match_one_item: bool = False
                    for text in not_allow:
                        if self.similar(text, item_text) > 0.6:
                            match_one_item = True
                            break
                    if match_one_item:
                        self.logger.debug('Not allowed to delete item. Skipping: {}', item_text)
                        trash += 1
                    else:
                        self.logger.info('Going to delete item: {}', item_text)
                        self._communicator.click(int(trashcancheck[trash].x), int(trashcancheck[trash].y))
                        time.sleep(1 + int(delayadd))

                        self._communicator.touch_and_hold(
                            click_x1, click_y, click_x2, click_y, click_duration)
                        time.sleep(1)

                        delx, dely = self._resocalc.get_confirm_delete_item_coords(self)
                        cur_time = time.time()
                        self._communicator.click(int(delx), int(dely))
                        deletion_timeout = 35
                        type_received, proto_entry = self._wait_for_data(timestamp=cur_time,
                                                                         proto_to_wait_for=ProtoIdentifier.INVENTORY,
                                                                         timeout=deletion_timeout)

                        if type_received != LatestReceivedType.UNDEFINED:
                            if type_received == LatestReceivedType.CLEAR:
                                success_counter += 1
                                self._clear_box_failcount = 0
                                self.set_devicesettings_value('last_cleanup_time', time.time())
                                delrounds_remaining -= 1
                                stop_screen_clear.set()
                                delete_allowed = True
                            else:
                                self.logger.warning("Did not receive confirmation of deletion of items in time")
                        else:
                            self.logger.warning('Deletion not confirmed within {}s for item: {}', deletion_timeout,
                                                item_text)
                            stop_screen_clear.set()
                            stop_inventory_clear.set()
                except UnicodeEncodeError:
                    self.logger.warning('Unable to identify item while ')
                    stop_inventory_clear.set()
                    stop_screen_clear.set()
                    pass

        x, y = self._resocalc.get_close_main_button_coords(self)
        self._communicator.click(int(x), int(y))
        time.sleep(1 + int(delayadd))
        return True

    def _update_injection_settings(self):
        injected_settings = {}
        scanmode = "quests"
        injected_settings["scanmode"] = scanmode
        ids_iv: List[int] = []
        self._encounter_ids = {}
        self._mitm_mapper.update_latest(origin=self._origin, key="ids_encountered", values_dict=self._encounter_ids)
        self._mitm_mapper.update_latest(origin=self._origin, key="ids_iv", values_dict=ids_iv)

        self._mitm_mapper.update_latest(origin=self._origin, key="injected_settings", values_dict=injected_settings)

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
            self.logger.debug("No GMO cells passed for surrounding cell check")
            return cells_with_forts
        # 35m radius around current location (thus cells that may be touched by that radius hopefully get included)
        s2cells_valid_around_location: List[CellId] = \
            S2Helper.get_s2cells_from_circle(self.current_location.lat,
                                             self.current_location.lng,
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
            self.logger.debug2("GMO cells around current position ({}) do not contain stops ", self.current_location)
        return cells_with_forts

    def _current_position_has_spinnable_stop(self, timestamp: float):
        type_received, data_received = self._wait_for_data(timestamp=timestamp, proto_to_wait_for=ProtoIdentifier.GMO)
        if type_received != LatestReceivedType.GMO or data_received is None:
            self._spinnable_data_failure()
            return False, False
        latest_proto = data_received.get("payload")
        gmo_cells: list = latest_proto.get("cells", None)

        if not gmo_cells:
            self.logger.warning("Can't spin stop - no map info in GMO!")
            self._spinnable_data_failure()
            return False, False

        cells_with_stops = self._directly_surrounding_gmo_cells_containing_stops_around_current_position(gmo_cells)
        for cell in cells_with_stops:
            forts: list = cell.get("forts", None)
            if not forts:
                continue

            for fort in forts:
                latitude: float = fort.get("latitude", 0.0)
                longitude: float = fort.get("longitude", 0.0)
                if latitude == 0.0 or longitude == 0.0:
                    continue
                elif (abs(self.current_location.lat - latitude) <= DISTANCE_TO_STOP_TO_CONSIDER_ON_TOP
                      and abs(self.current_location.lng - longitude) <= DISTANCE_TO_STOP_TO_CONSIDER_ON_TOP):
                    # We are basically on top of a stop
                    self.logger.info("Found stop/gym at current location!")
                else:
                    self.logger.debug2("Found stop nearby but not next to us to be spinned. Current lat, lng: {}, {}."
                                       "Stop at {}, {}", self.current_location.lat, self.current_location.lng,
                                       latitude, longitude)
                    continue

                fort_type: int = fort.get("type", 0)
                if fort_type == 0:
                    self._db_wrapper.delete_stop(latitude, longitude)
                    self.logger.warning("Tried to open a stop but found a gym instead!")
                    self._spinnable_data_failcount = 0
                    return False, True

                visited: bool = fort.get("visited", False)
                if self._level_mode and self._ignore_spinned_stops and visited:
                    self.logger.info("Level mode: Stop already visited - skipping it")
                    self._db_wrapper.submit_pokestop_visited(self._origin, latitude, longitude)
                    self._spinnable_data_failcount = 0
                    return False, True

                enabled: bool = fort.get("enabled", True)
                if not enabled:
                    self.logger.info("Can't spin the stop - it is disabled")
                closed: bool = fort.get("closed", False)
                if closed:
                    self.logger.info("Can't spin the stop - it is closed")
                cooldown: int = fort.get("cooldown_complete_ms", 0)
                if not cooldown == 0:
                    self.logger.info("Can't spin the stop - it has cooldown")
                self._spinnable_data_failcount = 0
                return fort_type == 1 and enabled and not closed and cooldown == 0, False
        # by now we should've found the stop in the GMO
        self.logger.warning("Unable to confirm the current location ({}) yielding a spinnable stop "
                            "- likely not standing exactly on top ...", str(self.current_location))
        self._check_if_stop_was_nearby_and_update_location(gmo_cells)
        self._spinnable_data_failure()
        return False, False

    def _try_to_open_pokestop(self, timestamp: float) -> LatestReceivedType:
        to = 0
        type_received: LatestReceivedType = LatestReceivedType.UNDEFINED
        proto_entry = None
        # let's first check the GMO for the stop we intend to visit and abort if it's disabled, a gym, whatsoever
        spinnable_stop, skip_recheck = self._current_position_has_spinnable_stop(timestamp)

        recheck_count = 0
        while not spinnable_stop and not skip_recheck and not recheck_count > 2:
            recheck_count += 1
            self.logger.info("Wait for new data to check the stop again ... (attempt {})", recheck_count + 1)
            type_received, proto_entry = self._wait_for_data(timestamp=time.time(),
                                                             proto_to_wait_for=ProtoIdentifier.GMO,
                                                             timeout=35)
            if type_received != LatestReceivedType.UNDEFINED:
                spinnable_stop, skip_recheck = self._current_position_has_spinnable_stop(timestamp)

        if not spinnable_stop:
            self.logger.info("Stop {}, {} considered to be ignored in the next round due to failed "
                             "spinnable check", self.current_location.lat, self.current_location.lng)
            self._mapping_manager.routemanager_add_coords_to_be_removed(self._routemanager_name,
                                                                        self.current_location.lat,
                                                                        self.current_location.lng)
            return type_received

        while type_received != LatestReceivedType.STOP and int(to) < 3:
            self._stop_process_time = math.floor(time.time())
            self._waittime_without_delays = self._stop_process_time
            self._click_pokestop_at_current_location(self._delay_add)
            self.set_devicesettings_value('last_action_time', time.time())
            type_received, proto_entry = self._wait_for_data(
                timestamp=self._stop_process_time, proto_to_wait_for=ProtoIdentifier.FORT_DETAILS, timeout=15)
            if type_received == LatestReceivedType.GYM:
                self.logger.info('Clicked GYM')
                time.sleep(10)
                x, y = self._resocalc.get_close_main_button_coords(
                    self)[0], self._resocalc.get_close_main_button_coords(self)[1]
                self._communicator.click(int(x), int(y))
                time.sleep(3)
                self._turn_map(self._delay_add)
                time.sleep(1)
            elif type_received == LatestReceivedType.MON:
                time.sleep(1)
                self.logger.info('Clicked MON')
                time.sleep(.5)
                self._turn_map(self._delay_add)
                time.sleep(1)
            elif type_received == LatestReceivedType.UNDEFINED:
                self.logger.info('Getting timeout - or other unknown error. Trying again')
                if not self._check_pogo_button():
                    self._check_pogo_close(takescreen=True)

            to += 1
            if to > 2:
                self.logger.warning("Giving up on this stop after 3 failures in open_pokestop loop")
        return type_received

    # TODO: handle https://github.com/Furtif/POGOProtos/blob/master/src/POGOProtos/Networking/Responses
    #  /FortSearchResponse.proto#L12
    def _handle_stop(self, timestamp: float):
        to = 0
        timeout = 35
        type_received: LatestReceivedType = LatestReceivedType.UNDEFINED
        data_received = FortSearchResultTypes.UNDEFINED

        while data_received != FortSearchResultTypes.QUEST and int(to) < 4:
            self.logger.info('Spin Stop')
            type_received, data_received = self._wait_for_data(
                timestamp=self._stop_process_time, proto_to_wait_for=ProtoIdentifier.FORT_SEARCH, timeout=timeout)

            if (type_received == LatestReceivedType.FORT_SEARCH_RESULT
                    and data_received == FortSearchResultTypes.INVENTORY):
                self.logger.info('Box is full... clear out items!')
                self.clear_thread_task = ClearThreadTasks.BOX
                time.sleep(5)
                if not self._mapping_manager.routemanager_redo_stop(self._routemanager_name, self._origin,
                                                                    self.current_location.lat,
                                                                    self.current_location.lng):
                    self.logger.warning('Cannot process this stop again')
                break
            elif (type_received == LatestReceivedType.FORT_SEARCH_RESULT
                    and (data_received == FortSearchResultTypes.QUEST
                         or data_received == FortSearchResultTypes.COOLDOWN
                         or (data_received == FortSearchResultTypes.FULL and self._level_mode))):
                if self._level_mode:
                    self.logger.info("Saving visitation info...")
                    self._latest_quest = math.floor(time.time())
                    self._db_wrapper.submit_pokestop_visited(self._origin,
                                                             self.current_location.lat,
                                                             self.current_location.lng)
                    # This is leveling mode, it's faster to just ignore spin result and continue ?
                    break

                if data_received == FortSearchResultTypes.COOLDOWN:
                    self.logger.info('Stop is on cooldown.. sleeping 10 seconds but probably should just move on')
                    time.sleep(10)
                    if self._db_wrapper.check_stop_quest(self.current_location.lat,
                                                         self.current_location.lng):
                        self.logger.info('Quest is done without us noticing. Getting new Quest...')
                    self.clear_thread_task = ClearThreadTasks.QUEST
                    break
                elif data_received == FortSearchResultTypes.QUEST:
                    self.logger.info('Received new Quest')
                    self._latest_quest = math.floor(time.time())

                if not self._enhanced_mode:
                    if not self._always_cleanup:
                        self._clear_quest_counter += 1
                        if self._clear_quest_counter == 3:
                            self.logger.info('Collected 3 quests - clean them')
                            reached_main_menu = self._check_pogo_main_screen(10, True)
                            if not reached_main_menu:
                                if not self._restart_pogo(mitm_mapper=self._mitm_mapper):
                                    # TODO: put in loop, count up for a reboot ;)
                                    raise InternalStopWorkerException
                            self.clear_thread_task = ClearThreadTasks.QUEST
                            self._clear_quest_counter = 0
                    else:
                        self.logger.info('Getting new quest - clean it')
                        reached_main_menu = self._check_pogo_main_screen(10, True)
                        if not reached_main_menu:
                            if not self._restart_pogo(mitm_mapper=self._mitm_mapper):
                                # TODO: put in loop, count up for a reboot ;)
                                raise InternalStopWorkerException
                        self.clear_thread_task = ClearThreadTasks.QUEST
                    break

            elif (type_received == LatestReceivedType.FORT_SEARCH_RESULT
                    and (data_received == FortSearchResultTypes.TIME
                         or data_received == FortSearchResultTypes.OUT_OF_RANGE)):
                self.logger.warning('Softban - return to main screen and open again...')
                on_main_menu = self._check_pogo_main_screen(10, False)
                if not on_main_menu:
                    self._restart_pogo(mitm_mapper=self._mitm_mapper)
                self._stop_process_time = math.floor(time.time())
                if self._try_to_open_pokestop(self._stop_process_time) == LatestReceivedType.UNDEFINED:
                    return
            elif (type_received == LatestReceivedType.FORT_SEARCH_RESULT
                    and data_received == FortSearchResultTypes.FULL):
                self.logger.warning("Failed getting quest but got items - quest box is probably full. Starting cleanup "
                                    "routine.")
                reached_main_menu = self._check_pogo_main_screen(10, True)
                if not reached_main_menu:
                    if not self._restart_pogo(mitm_mapper=self._mitm_mapper):
                        # TODO: put in loop, count up for a reboot ;)
                        raise InternalStopWorkerException
                self.clear_thread_task = ClearThreadTasks.QUEST
                self._clear_quest_counter = 0
                break
            else:
                if data_received == LatestReceivedType.MON:
                    self.logger.info("Got MON data after opening stop. This does not make sense - just retry...")
                else:
                    self.logger.info("Brief speed lock or we already spun it, trying again")
                if to > 2 and self._db_wrapper.check_stop_quest(self.current_location.lat,
                                                                self.current_location.lng):
                    self.logger.info('Quest is done without us noticing. Getting new Quest...')
                    if not self._enhanced_mode:
                        self.clear_thread_task = ClearThreadTasks.QUEST
                    break
                elif to > 2 and self._level_mode and self._mitm_mapper.get_poke_stop_visits(
                        self._origin) > 6800:
                    self.logger.warning("Might have hit a spin limit for worker! We have spun: {} stops",
                                        self._mitm_mapper.get_poke_stop_visits(self._origin))

                self._turn_map(self._delay_add)
                time.sleep(1)
                self._stop_process_time = math.floor(time.time())
                if self._try_to_open_pokestop(self._stop_process_time) == LatestReceivedType.UNDEFINED:
                    return
                to += 1
                if to > 3:
                    self.logger.warning("giving up spinning after 4 tries in handle_stop loop")

        self.set_devicesettings_value('last_action_time', time.time())

    def _check_for_data_content(self, latest, proto_to_wait_for: ProtoIdentifier, timestamp: float) \
            -> Tuple[LatestReceivedType, Optional[Union[dict, FortSearchResultTypes]]]:
        type_of_data_found: LatestReceivedType = LatestReceivedType.UNDEFINED
        data_found: Optional[object] = None
        # Check if we have clicked a gym or mon...
        if ProtoIdentifier.GYM_INFO.value in latest \
                and latest[ProtoIdentifier.GYM_INFO.value].get('timestamp', 0) >= timestamp:
            type_of_data_found = LatestReceivedType.GYM
            return type_of_data_found, data_found
        elif ProtoIdentifier.ENCOUNTER.value in latest \
                and latest[ProtoIdentifier.ENCOUNTER.value].get('timestamp', 0) >= timestamp:
            type_of_data_found = LatestReceivedType.MON
            return type_of_data_found, data_found
        elif proto_to_wait_for.value not in latest:
            self.logger.debug("No data linked to the requested proto since MAD started.")
            return type_of_data_found, data_found

        # when waiting for stop or spin data, it is enough to make sure
        # our data is newer than the latest of last quest received, last
        # successful bag clear or last successful quest clear. This eliminates
        # the need to add arbitrary timedeltas for possible small delays,
        # which we don't do in other workers either
        if proto_to_wait_for in [ProtoIdentifier.FORT_SEARCH, ProtoIdentifier.FORT_DETAILS]:
            potential_replacements = [
                self._latest_quest,
                self.get_devicesettings_value('last_cleanup_time', 0),
                self.get_devicesettings_value('last_questclear_time', 0)
            ]
            replacement = max(x for x in potential_replacements if isinstance(x, int) or isinstance(x, float))
            self.logger.debug("timestamp {} being replaced with {} because we're waiting for proto {}",
                              datetime.fromtimestamp(timestamp).strftime('%H:%M:%S'),
                              datetime.fromtimestamp(replacement).strftime('%H:%M:%S'),
                              proto_to_wait_for)
            timestamp = replacement
        # proto has previously been received, let's check the timestamp...
        latest_proto_entry = latest.get(proto_to_wait_for.value, None)
        if not latest_proto_entry:
            self.logger.debug("No data linked to the requested proto since MAD started.")
            return type_of_data_found, data_found
        timestamp_of_proto = latest_proto_entry.get("timestamp", 0)
        if timestamp_of_proto < timestamp:
            self.logger.debug("latest timestamp of proto {} ({}) is older than {}", proto_to_wait_for,
                              timestamp_of_proto, timestamp)
            # TODO: timeout error instead of data_error_counter? Differentiate timeout vs missing data (the
            # TODO: latter indicates too high speeds for example
            return type_of_data_found, data_found

        # TODO: consider reseting timestamp here since we clearly received SOMETHING
        latest_proto_data = latest_proto_entry.get("values", None)
        self.logger.debug4("Latest data received: {}", latest_proto_data)
        if latest_proto_data is None:
            return type_of_data_found, data_found
        latest_proto = latest_proto_data.get("payload", None)
        self.logger.debug2("Checking for Quest related data in proto {}", proto_to_wait_for)
        if latest_proto is None:
            self.logger.debug("No proto data for {} at {} after {}", proto_to_wait_for,
                              timestamp_of_proto, timestamp)
        elif proto_to_wait_for == ProtoIdentifier.FORT_SEARCH:
            quest_type: int = latest_proto.get('challenge_quest', {})\
                .get('quest', {})\
                .get('quest_type', False)
            result: int = latest_proto.get("result", 0)
            if result == 1 and len(latest_proto.get('items_awarded', [])) == 0:
                return LatestReceivedType.FORT_SEARCH_RESULT, FortSearchResultTypes.TIME
            elif result == 1 and quest_type == 0:
                return LatestReceivedType.FORT_SEARCH_RESULT, FortSearchResultTypes.FULL
            elif result == 1 and len(latest_proto.get('items_awarded', [])) > 0:
                return LatestReceivedType.FORT_SEARCH_RESULT, FortSearchResultTypes.QUEST
            elif result == 2:
                return LatestReceivedType.FORT_SEARCH_RESULT, FortSearchResultTypes.OUT_OF_RANGE
            elif result == 3:
                return LatestReceivedType.FORT_SEARCH_RESULT, FortSearchResultTypes.COOLDOWN
            elif result == 4:
                return LatestReceivedType.FORT_SEARCH_RESULT, FortSearchResultTypes.INVENTORY
            elif result == 5:
                return LatestReceivedType.FORT_SEARCH_RESULT, FortSearchResultTypes.LIMIT
        elif proto_to_wait_for == ProtoIdentifier.FORT_DETAILS:
            fort_type: int = latest_proto.get("type", 0)
            data_found = latest_proto
            type_of_data_found = LatestReceivedType.GYM if fort_type == 0 else LatestReceivedType.STOP
        elif proto_to_wait_for == ProtoIdentifier.GMO \
                and self._directly_surrounding_gmo_cells_containing_stops_around_current_position(
                    latest_proto.get("cells")):
            data_found = latest_proto_data
            type_of_data_found = LatestReceivedType.GMO
        elif proto_to_wait_for == ProtoIdentifier.INVENTORY and 'inventory_delta' in latest_proto and \
                len(latest_proto['inventory_delta']['inventory_items']) > 0:
            type_of_data_found = LatestReceivedType.CLEAR
            data_found = latest_proto

        return type_of_data_found, data_found

    def _spinnable_data_failure(self):
        if self._spinnable_data_failcount > 9:
            self._spinnable_data_failcount = 0
            self.logger.warning("Worker failed spinning stop with GMO/data issues 10+ times - restart pogo")
            if not self._restart_pogo(mitm_mapper=self._mitm_mapper):
                # TODO: put in loop, count up for a reboot ;)
                raise InternalStopWorkerException
        else:
            self._spinnable_data_failcount += 1

    def _check_if_stop_was_nearby_and_update_location(self, gmo_cells):
        self.logger.info("Checking stops around current location ({}) for deleted stops.", self.current_location)
        stops: Dict[str, Tuple[Location, datetime]] = self._db_wrapper.get_stop_ids_and_locations_nearby(
            self.current_location
        )
        self.logger.debug("Checking if GMO contains location changes or DB has stops that are already deleted. In DB: "
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
                    self.logger.warning("Cannot process fort without id, lat or lon")
                    continue
                location_last_updated: Tuple[Location, datetime] = stops.get(fort_id)
                if location_last_updated is None:
                    # new stop we have not seen before, MITM processors should take care of that
                    self.logger.debug2("Stop not in DB (in range) with ID {} at {}, {}", fort_id, latitude, longitude)
                    continue
                else:
                    stops.pop(fort_id)
                stop_location_known, last_updated = location_last_updated
                if stop_location_known.lat == latitude and stop_location_known.lng == longitude:
                    # Location of fort has not changed
                    self.logger.debug2("Fort {} has not moved", fort_id)
                    continue
                else:
                    # now we have a location from DB for the given stop we are currently processing but does not equal
                    # the one we are currently processing, thus SAME fort_id
                    # now update the stop
                    self.logger.warning("Updating fort {} with previous location {} now placed at {}, {}",
                                        fort_id, str(stop_location_known), latitude, longitude)
                    self._db_wrapper.update_pokestop_location(fort_id, latitude, longitude)

        timedelta_to_consider_deletion = timedelta(days=3)
        for fort_id in stops.keys():
            # Call delete of stops that have been not been found within 100m range of current position
            stop_location_known, last_updated = stops[fort_id]
            self.logger.debug("Considering stop {} at {} (last updated {}) for deletion",
                              fort_id, stop_location_known, last_updated)
            if last_updated and last_updated > datetime.now() - timedelta_to_consider_deletion:
                self.logger.debug3("Stop considered for deletion was last updated recently, not gonna delete it for"
                                   "now.", last_updated)
                continue
            distance_to_location = get_distance_of_two_points_in_meters(float(stop_location_known.lat),
                                                                        float(stop_location_known.lng),
                                                                        float(self.current_location.lat),
                                                                        float(self.current_location.lng))
            self.logger.debug("Distance to {} at {} (last updated {})",
                              fort_id, stop_location_known, last_updated)
            if distance_to_location < 100:
                self.logger.warning(
                    "Deleting stop {} at {} since it could not be found in the GMO but was present in DB and within "
                    "100m of worker ({}m) and was last updated more than 3 days ago ()",
                    fort_id, str(stop_location_known), distance_to_location, last_updated)
                self._db_wrapper.delete_stop(stop_location_known.lat, stop_location_known.lng)
                self._mapping_manager.routemanager_add_coords_to_be_removed(self._routemanager_name,
                                                                            stop_location_known.lat,
                                                                            stop_location_known.lng)
