import math
import time
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from enum import Enum
from threading import Event, Thread
from typing import List
from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.mitm_receiver.MitmMapper import MitmMapper
from mapadroid.ocr.pogoWindows import PogoWindows
from mapadroid.utils import MappingManager
from mapadroid.utils.collections import Location
from mapadroid.utils.geo import (
    get_distance_of_two_points_in_meters,
    get_lat_lng_offsets_by_distance
)
from mapadroid.utils.madGlobals import (
    InternalStopWorkerException,
    WebsocketWorkerRemovedException,
    WebsocketWorkerTimeoutException,
    WebsocketWorkerConnectionClosedException
)
from mapadroid.websocket.AbstractCommunicator import AbstractCommunicator
from mapadroid.worker.MITMBase import MITMBase, LatestReceivedType
from mapadroid.utils.logging import get_logger, LoggerEnums


logger = get_logger(LoggerEnums.worker)
PROTO_NUMBER_FOR_GMO = 106


class FortSearchResultTypes(Enum):
    UNDEFINED = 0
    QUEST = 1
    TIME = 2
    COOLDOWN = 3
    INVENTORY = 4
    LIMIT = 5
    UNAVAILABLE = 6
    OUT_OF_RANGE = 7
    FULL = 8


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
                          mitm_mapper=mitm_mapper, pogo_win_manager=pogo_window_manager, walker=walker,
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
                self.logger.error('Something happened while account rotation')
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
        if not self._mapping_manager.routemanager_present(self._routemanager_name) \
                or self._stop_worker_event.is_set():
            raise InternalStopWorkerException

        routemanager_settings = self._mapping_manager.routemanager_get_settings(self._routemanager_name)

        distance = get_distance_of_two_points_in_meters(float(self.last_location.lat),
                                                        float(
                                                            self.last_location.lng),
                                                        float(
                                                            self.current_location.lat),
                                                        float(self.current_location.lng))
        self.logger.debug('Moving {} meters to the next position', round(distance, 2))

        delay_used = 0
        self.logger.debug("Getting time")
        speed = routemanager_settings.get("speed", 0)
        max_distance = routemanager_settings.get("max_distance", None)
        if (speed == 0 or (max_distance and 0 < max_distance < distance) or
                (self.last_location.lat == 0.0 and self.last_location.lng == 0.0)):
            self.logger.debug("main: Teleporting...")
            self._transporttype = 0
            self._communicator.set_location(
                Location(self.current_location.lat, self.current_location.lng), 0)
            # the time we will take as a starting point to wait for data...
            cur_time = math.floor(time.time())

            delay_used = self.get_devicesettings_value('post_teleport_delay', 7)
            speed = 16.67  # Speed can be 60 km/h up to distances of 3km

            if self.last_location.lat == 0.0 and self.last_location.lng == 0.0:
                self.logger.info('Starting fresh round - using lower delay')
                delay_used = self.get_devicesettings_value('post_teleport_delay', 7)
            else:
                if distance >= 1335000:
                    speed = 180.43  # Speed can be abt 650 km/h
                elif distance >= 1100000:
                    speed = 176.2820513
                elif distance >= 1020000:
                    speed = 168.3168317
                elif distance >= 1007000:
                    speed = 171.2585034
                elif distance >= 948000:
                    speed = 166.3157895
                elif distance >= 900000:
                    speed = 164.8351648
                elif distance >= 897000:
                    speed = 166.1111111
                elif distance >= 839000:
                    speed = 158.9015152
                elif distance >= 802000:
                    speed = 159.1269841
                elif distance >= 751000:
                    speed = 152.6422764
                elif distance >= 700000:
                    speed = 151.5151515
                elif distance >= 650000:
                    speed = 146.3963964
                elif distance >= 600000:
                    speed = 142.8571429
                elif distance >= 550000:
                    speed = 138.8888889
                elif distance >= 500000:
                    speed = 134.4086022
                elif distance >= 450000:
                    speed = 129.3103448
                elif distance >= 400000:
                    speed = 123.4567901
                elif distance >= 350000:
                    speed = 116.6666667
                elif distance >= 328000:
                    speed = 113.8888889
                elif distance >= 300000:
                    speed = 108.6956522
                elif distance >= 250000:
                    speed = 101.6260163
                elif distance >= 201000:
                    speed = 90.54054054
                elif distance >= 175000:
                    speed = 85.78431373
                elif distance >= 150000:
                    speed = 78.125
                elif distance >= 125000:
                    speed = 71.83908046
                elif distance >= 100000:
                    speed = 64.1025641
                elif distance >= 90000:
                    speed = 60
                elif distance >= 80000:
                    speed = 55.55555556
                elif distance >= 70000:
                    speed = 50.72463768
                elif distance >= 60000:
                    speed = 47.61904762
                elif distance >= 45000:
                    speed = 39.47368421
                elif distance >= 40000:
                    speed = 35.0877193
                elif distance >= 35000:
                    speed = 32.40740741
                elif distance >= 30000:
                    speed = 29.41176471
                elif distance >= 25000:
                    speed = 27.77777778
                elif distance >= 20000:
                    speed = 27.77777778
                elif distance >= 15000:
                    speed = 27.77777778
                elif distance >= 10000:
                    speed = 23.80952381
                elif distance >= 8000:
                    speed = 26.66666667
                elif distance >= 5000:
                    speed = 22.34137623
                elif distance >= 4000:
                    speed = 22.22222222

                delay_used = distance / speed

                if delay_used > 7200:  # There's a maximum of 2 hours wait time
                    delay_used = 7200
            self.logger.debug(
                "Need more sleep after Teleport: {} seconds!", int(delay_used))
        else:
            delay_used = distance / speed
            self.logger.info("main: Walking {} m, this will take {} seconds", distance, delay_used)
            self._transporttype = 1
            self._communicator.walk_from_to(self.last_location, self.current_location, speed)
            # the time we will take as a starting point to wait for data...
            cur_time = math.floor(time.time())
            delay_used = self.get_devicesettings_value('post_walk_delay', 7)

        walk_distance_post_teleport = self.get_devicesettings_value('walk_after_teleport_distance', 0)
        if 0 < walk_distance_post_teleport < distance:
            # TODO: actually use to_walk for distance
            lat_offset, lng_offset = get_lat_lng_offsets_by_distance(
                walk_distance_post_teleport)

            to_walk = get_distance_of_two_points_in_meters(float(self.current_location.lat),
                                                           float(
                                                               self.current_location.lng),
                                                           float(
                                                               self.current_location.lat) + lat_offset,
                                                           float(self.current_location.lng) + lng_offset)
            self.logger.info("Walking roughly: {:.2f}m", to_walk)
            time.sleep(0.3)
            self._communicator.walk_from_to(self.current_location,
                                            Location(self.current_location.lat + lat_offset,
                                                     self.current_location.lng + lng_offset),
                                            11)
            self.logger.debug("Walking back")
            time.sleep(0.3)
            self._communicator.walk_from_to(Location(self.current_location.lat + lat_offset,
                                                     self.current_location.lng + lng_offset),
                                            self.current_location,
                                            11)
            self.logger.debug("Done walking")
            time.sleep(1)
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

        if self.get_devicesettings_value('screendetection', False) and \
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
                data_received = self._open_pokestop(self._stop_process_time)
                if data_received is not None and data_received == LatestReceivedType.STOP:
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
                     'Élément', 'mystérieux', 'Mysterious', 'Component', 'Mysteriöses')
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
                self.logger.error('Could not find any trashcans - abort')
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
                        self.logger.error("Did not get any text in inventory")
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
                        curTime = time.time()
                        self._communicator.click(int(delx), int(dely))

                        deletion_timeout = 35
                        data_received = self._wait_for_data(
                            timestamp=curTime, proto_to_wait_for=4, timeout=deletion_timeout)

                        if data_received != LatestReceivedType.UNDEFINED:
                            if data_received == LatestReceivedType.CLEAR:
                                success_counter += 1
                                self._clear_box_failcount = 0
                                self.set_devicesettings_value('last_cleanup_time', time.time())
                                delrounds_remaining -= 1
                                stop_screen_clear.set()
                                delete_allowed = True
                        else:
                            self.logger.error('Deletion not confirmed within {}s for item: {}', deletion_timeout,
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
        routemanager_settings = self._mapping_manager.routemanager_get_settings(self._routemanager_name)
        ids_iv: List[int] = []
        if routemanager_settings is not None:
            ids_iv = self._mapping_manager.get_monlist(routemanager_settings.get("mon_ids_iv", None),
                                                       self._routemanager_name)
        # if iv ids are specified we will sync the workers encountered ids to newest time.
        if ids_iv is not None:
            (self._latest_encounter_update, encounter_ids) = self._db_wrapper.update_encounters_from_db(
                self._mapping_manager.routemanager_get_geofence_helper(self._routemanager_name),
                self._latest_encounter_update)
            if encounter_ids:
                self.logger.debug("Found {} new encounter_ids", len(encounter_ids))
                for encounter_id, disappear in encounter_ids.items():
                    self.logger.debug("id: {}, despawn: {}", encounter_id, disappear)
            self._encounter_ids = {**encounter_ids, **self._encounter_ids}
            # allow one minute extra life time, because the clock on some devices differs, newer got why this problem
            # apears but it is a fact.
            max_age = time.time() - 60

            remove = []
            for key, value in self._encounter_ids.items():
                if value < max_age:
                    remove.append(key)
                    self.logger.debug("removing encounterid: {} mon despawned", key)

            for key in remove:
                del self._encounter_ids[key]

            self.logger.debug("Encounter list len: {}", len(self._encounter_ids))
            # TODO: here we have the latest update of encountered mons.
            # self._encounter_ids contains the complete dict.
            # encounter_ids only contains the newest update.
        self._mitm_mapper.update_latest(origin=self._origin, key="ids_encountered", values_dict=self._encounter_ids)
        self._mitm_mapper.update_latest(origin=self._origin, key="ids_iv", values_dict=ids_iv)

        self._mitm_mapper.update_latest(origin=self._origin, key="injected_settings", values_dict=injected_settings)

    def _current_position_has_spinnable_stop(self, timestamp: float):
        latest: dict = self._mitm_mapper.request_latest(self._origin)
        if latest is None or PROTO_NUMBER_FOR_GMO not in latest.keys():
            self.logger.warning("Can't spin stop - no GMO data available!")
            return False, False

        gmo_cells: list = latest.get(PROTO_NUMBER_FOR_GMO).get("values", {}).get("payload", {}).get("cells",
                                                                                                    None)
        if gmo_cells == list():
            self.logger.warning("Can't spin stop - no map info in GMO!")
            return False, False
        for cell in gmo_cells:
            # each cell contains an array of forts, check each cell for a fort with our current location (maybe +-
            # very very little jitter) and check its properties
            forts: list = cell.get("forts", None)
            if forts is None:
                continue

            for fort in forts:

                latitude: float = fort.get("latitude", 0.0)
                longitude: float = fort.get("longitude", 0.0)
                if latitude == 0.0 or longitude == 0.0:
                    continue
                elif (abs(self.current_location.lat - latitude) > 0.00003 or
                      abs(self.current_location.lng - longitude) > 0.00003):
                    continue

                fort_type: int = fort.get("type", 0)
                if fort_type == 0:
                    self._db_wrapper.delete_stop(latitude, longitude)
                    self.logger.warning("Tried to open a stop but found a gym instead!")
                    return False, True

                visited: bool = fort.get("visited", False)
                if self._level_mode and self._ignore_spinned_stops and visited:
                    self.logger.info("Level mode: Stop already visited - skipping it")
                    self._db_wrapper.submit_pokestop_visited(self._origin, latitude, longitude)
                    return False, True

                enabled: bool = fort.get("enabled", True)
                if not enabled:
                    self.logger.warning("Can't spin the stop - it is disabled")
                closed: bool = fort.get("closed", False)
                if closed:
                    self.logger.warning("Can't spin the stop - it is closed")
                cooldown: int = fort.get("cooldown_complete_ms", 0)
                if not cooldown == 0:
                    self.logger.warning("Can't spin the stop - it has cooldown")
                return fort_type == 1 and enabled and not closed and cooldown == 0, False
        # by now we should've found the stop in the GMO
        # TODO: consider counter in DB for stop and delete if N reached, reset when updating with GMO
        self.logger.warning("Can't spin stop - couldn't find it closeby!")
        return False, False

    def _open_pokestop(self, timestamp: float):
        to = 0
        data_received = LatestReceivedType.UNDEFINED

        # let's first check the GMO for the stop we intend to visit and abort if it's disabled, a gym, whatsoever
        spinnable_stop, skip_recheck = self._current_position_has_spinnable_stop(timestamp)
        if not spinnable_stop:
            if not skip_recheck:
                # wait for GMO in case we moved too far away
                data_received = self._wait_for_data(
                    timestamp=timestamp, proto_to_wait_for=106, timeout=35)
                if data_received != LatestReceivedType.UNDEFINED:
                    spinnable_stop, _ = self._current_position_has_spinnable_stop(timestamp)
                    if not spinnable_stop:
                        self.logger.info("Stop {}, {} considered to be ignored in the next round due to failed "
                                         "spinnable check", self.current_location.lat, self.current_location.lng)
                        self._mapping_manager.routemanager_add_coords_to_be_removed(self._routemanager_name,
                                                                                    self.current_location.lat,
                                                                                    self.current_location.lng)
                        return None
            else:
                return None
        while data_received != LatestReceivedType.STOP and int(to) < 3:
            self._stop_process_time = math.floor(time.time())
            self._waittime_without_delays = self._stop_process_time
            self._open_gym(self._delay_add)
            self.set_devicesettings_value('last_action_time', time.time())
            data_received = self._wait_for_data(
                timestamp=self._stop_process_time, proto_to_wait_for=104, timeout=15)
            if data_received == LatestReceivedType.GYM:
                self.logger.info('Clicking GYM')
                time.sleep(10)
                x, y = self._resocalc.get_close_main_button_coords(
                    self)[0], self._resocalc.get_close_main_button_coords(self)[1]
                self._communicator.click(int(x), int(y))
                time.sleep(3)
                self._turn_map(self._delay_add)
                time.sleep(1)
            elif data_received == LatestReceivedType.MON:
                time.sleep(1)
                self.logger.info('Clicking MON')
                time.sleep(.5)
                self._turn_map(self._delay_add)
                time.sleep(1)
            elif data_received == LatestReceivedType.UNDEFINED:
                self.logger.info('Getting timeout - or other unknown error. Try again')
                if not self._check_pogo_button():
                    self._check_pogo_close(takescreen=True)

            to += 1
            if to > 2:
                self.logger.warning("Giving up on this stop after 3 failures in open_pokestop loop")
        return data_received

    # TODO: handle https://github.com/Furtif/POGOProtos/blob/master/src/POGOProtos/Networking/Responses
    #  /FortSearchResponse.proto#L12
    def _handle_stop(self, timestamp: float):
        to = 0
        timeout = 35
        data_received = FortSearchResultTypes.UNDEFINED

        while data_received != FortSearchResultTypes.QUEST and int(to) < 4:
            self.logger.info('Spin Stop')
            data_received = self._wait_for_data(
                timestamp=self._stop_process_time, proto_to_wait_for=101, timeout=timeout)
            time.sleep(1)
            if data_received == FortSearchResultTypes.INVENTORY:
                self.logger.info('Box is full... clear out items!')
                self.clear_thread_task = ClearThreadTasks.BOX
                time.sleep(5)
                if not self._mapping_manager.routemanager_redo_stop(self._routemanager_name, self._origin,
                                                                    self.current_location.lat,
                                                                    self.current_location.lng):
                    self.logger.warning('Cannot process this stop again')
                break
            elif data_received == FortSearchResultTypes.QUEST or data_received == FortSearchResultTypes.COOLDOWN or \
                    (data_received == FortSearchResultTypes.FULL and self._level_mode):
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
                    if not self._enhanced_mode:
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

            elif (data_received == FortSearchResultTypes.TIME or data_received ==
                  FortSearchResultTypes.OUT_OF_RANGE):
                self.logger.warning('Softban - return to main screen and open again...')
                on_main_menu = self._check_pogo_main_screen(10, False)
                if not on_main_menu:
                    self._restart_pogo(mitm_mapper=self._mitm_mapper)
                self._stop_process_time = math.floor(time.time())
                if self._open_pokestop(self._stop_process_time) is None:
                    return
            elif data_received == FortSearchResultTypes.FULL:
                self.logger.warning("Failed getting quest but got items - quest box is probably full. Start cleanup.")
                reached_main_menu = self._check_pogo_main_screen(10, True)
                if not reached_main_menu:
                    if not self._restart_pogo(mitm_mapper=self._mitm_mapper):
                        # TODO: put in loop, count up for a reboot ;)
                        raise InternalStopWorkerException
                if not self._enhanced_mode:
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
                if self._open_pokestop(self._stop_process_time) is None:
                    return
                to += 1
                if to > 3:
                    self.logger.warning("giving up spinning after 4 tries in handle_stop loop")

        self.set_devicesettings_value('last_action_time', time.time())

    def _wait_data_worker(self, latest, proto_to_wait_for, timestamp):
        if latest is None:
            self.logger.debug("Nothing received since MAD started")
            time.sleep(0.5)
        elif 156 in latest and latest[156].get('timestamp', 0) >= timestamp:
            return LatestReceivedType.GYM
        elif 102 in latest and latest[102].get('timestamp', 0) >= timestamp:
            return LatestReceivedType.MON
        elif proto_to_wait_for not in latest:
            self.logger.debug("No data linked to the requested proto since MAD started.")
            time.sleep(0.5)
        else:
            # when waiting for stop or spin data, it is enough to make sure
            # our data is newer than the latest of last quest received, last
            # successful bag clear or last successful quest clear. This eliminates
            # the need to add arbitrary timedeltas for possible small delays,
            # which we don't do in other workers either
            if proto_to_wait_for in [101, 104]:
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
            # TODO: int vs str-key?
            latest_proto = latest.get(proto_to_wait_for, None)
            latest_timestamp = latest_proto.get("timestamp", 0)
            if latest_timestamp >= timestamp:
                # TODO: consider reseting timestamp here since we clearly received SOMETHING
                latest_data = latest_proto.get("values", None)
                self.logger.debug4("Latest data received: {}", latest_data)
                if latest_data is None:
                    time.sleep(0.5)
                    return None
                elif proto_to_wait_for == 101:
                    payload: dict = latest_data.get("payload", None)
                    if payload is None:
                        return None
                    quest_type: int = payload.get('challenge_quest', {}) \
                                             .get('quest', {}) \
                                             .get('quest_type', False)
                    result: int = payload.get("result", 0)
                    if result == 1 and len(payload.get('items_awarded', [])) == 0:
                        return FortSearchResultTypes.TIME
                    elif result == 1 and quest_type == 0:
                        return FortSearchResultTypes.FULL
                    elif result == 1 and len(payload.get('items_awarded', [])) > 0:
                        return FortSearchResultTypes.QUEST
                    elif result == 2:
                        return FortSearchResultTypes.OUT_OF_RANGE
                    elif result == 3:
                        return FortSearchResultTypes.COOLDOWN
                    elif result == 4:
                        return FortSearchResultTypes.INVENTORY
                    elif result == 5:
                        return FortSearchResultTypes.LIMIT
                elif proto_to_wait_for == 104:
                    fort_type: int = latest_data.get("payload").get("type", 0)
                    if fort_type == 0:
                        return LatestReceivedType.GYM
                    else:
                        return LatestReceivedType.STOP
                elif proto_to_wait_for == 106:
                    for data_extract in latest_data['payload']['cells']:
                        for forts in data_extract['forts']:
                            if forts['id']:
                                return LatestReceivedType.GMO
                if proto_to_wait_for == 4 and 'inventory_delta' in latest_data['payload'] and \
                        len(latest_data['payload']['inventory_delta']['inventory_items']) > 0:
                    return LatestReceivedType.CLEAR
            else:
                self.logger.debug("latest timestamp of proto {} ({}) is older than {}", proto_to_wait_for,
                                  latest_timestamp, timestamp)
                # TODO: timeoutopen error instead of data_error_counter? Differentiate timeout vs missing data (the
                # TODO: latter indicates too high speeds for example
                time.sleep(0.5)
        return LatestReceivedType.UNDEFINED
