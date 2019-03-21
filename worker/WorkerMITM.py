import logging
import math
import time

from route.RouteManagerIV import RouteManagerIV
from utils.geo import get_distance_of_two_points_in_meters, get_lat_lng_offsets_by_distance
from utils.madGlobals import InternalStopWorkerException
from worker.MITMBase import MITMBase

log = logging.getLogger(__name__)


class WorkerMITM(MITMBase):
    def _valid_modes(self):
        return ["iv_mitm", "raids_mitm", "mon_mitm"]

    def _health_check(self):
        log.debug("_health_check: called")
        pass

    def _cleanup(self):
        # no additional cleanup in MITM yet
        pass

    def _post_move_location_routine(self, timestamp):
        # TODO: pass the appropiate proto number if IV?
        self._wait_for_data(timestamp)

    def _move_to_location(self):
        routemanager = self._get_currently_valid_routemanager()
        if routemanager is None:
            raise InternalStopWorkerException
        # get the distance from our current position (last) to the next gym (cur)
        distance = get_distance_of_two_points_in_meters(float(self._devicesettings["last_location"].lat),
                                                        float(self._devicesettings["last_location"].lng),
                                                        float(self.current_location.lat),
                                                        float(self.current_location.lng))
        log.info('main: Moving %s meters to the next position' % distance)
        delay_used = 0
        log.debug("Getting time")
        speed = routemanager.settings.get("speed", 0)
        max_distance = routemanager.settings.get("max_distance", None)
        if (speed == 0 or
                (max_distance and 0 < max_distance < distance)
                or (self._devicesettings["last_location"].lat == 0.0 and
                    self._devicesettings["last_location"].lng == 0.0)):
            log.info("main: Teleporting...")
            self._communicator.setLocation(self.current_location.lat, self.current_location.lng, 0)
            cur_time = math.floor(time.time())  # the time we will take as a starting point to wait for data...

            delay_used = self._devicesettings.get('post_teleport_delay', 7)
            # Test for cooldown / teleported distance TODO: check this block...
            if self._devicesettings.get('cool_down_sleep', False):
                if distance > 2500:
                    delay_used = 8
                elif distance > 5000:
                    delay_used = 10
                elif distance > 10000:
                    delay_used = 15
                log.info("Need more sleep after Teleport: %s seconds!" % str(delay_used))
                # curTime = math.floor(time.time())  # the time we will take as a starting point to wait for data...
            walk_distance_post_teleport = self._devicesettings.get('walk_after_teleport_distance', 0)
            if 0 < walk_distance_post_teleport < distance:
                # TODO: actually use to_walk for distance
                lat_offset, lng_offset = get_lat_lng_offsets_by_distance(walk_distance_post_teleport)

                to_walk = get_distance_of_two_points_in_meters(float(self.current_location.lat),
                                                               float(self.current_location.lng),
                                                               float(self.current_location.lat) + lat_offset,
                                                               float(self.current_location.lng) + lng_offset)
                log.info("Walking roughly: %s" % str(to_walk))
                time.sleep(0.3)
                self._communicator.walkFromTo(self.current_location.lat,
                                              self.current_location.lng,
                                              self.current_location.lat + lat_offset,
                                              self.current_location.lng + lng_offset,
                                              11)
                log.debug("Walking back")
                time.sleep(0.3)
                self._communicator.walkFromTo(self.current_location.lat + lat_offset,
                                              self.current_location.lng + lng_offset,
                                              self.current_location.lat,
                                              self.current_location.lng,
                                              11)
                log.debug("Done walking")
                time.sleep(1)
        else:
            log.info("main: Walking...")
            self._communicator.walkFromTo(self._devicesettings["last_location"].lat,
                                          self._devicesettings["last_location"].lng,
                                          self.current_location.lat, self.current_location.lng, speed)
            cur_time = math.floor(time.time())  # the time we will take as a starting point to wait for data...
            delay_used = self._devicesettings.get('post_walk_delay', 7)
        log.info("Sleeping %s" % str(delay_used))
        time.sleep(float(delay_used))
        self._devicesettings["last_location"] = self.current_location
        return cur_time, True

    def _pre_location_update(self):
        self.__update_injection_settings()

    def _pre_work_loop(self):
        log.info("MITM worker starting")

    def _start_pogo(self):
        pogo_topmost = self._communicator.isPogoTopmost()
        if pogo_topmost:
            return True

        if not self._communicator.isScreenOn():
            self._communicator.startApp("de.grennith.rgc.remotegpscontroller")
            log.warning("Turning screen on")
            self._communicator.turnScreenOn()
            time.sleep(self._devicesettings.get("post_turn_screen_on_delay", 7))

        cur_time = time.time()
        start_result = False
        while not pogo_topmost:
            start_result = self._communicator.startApp("com.nianticlabs.pokemongo")
            time.sleep(1)
            pogo_topmost = self._communicator.isPogoTopmost()
        reached_raidtab = False
        if start_result:
            log.warning("startPogo: Starting pogo...")
            time.sleep(self._devicesettings.get("post_pogo_start_delay", 60))
            self._last_known_state["lastPogoRestart"] = cur_time

            # let's handle the login and stuff
            reached_raidtab = True

        return reached_raidtab

    def __init__(self, args, id, last_known_state, websocket_handler, route_manager_daytime, route_manager_nighttime,
                 mitm_mapper, devicesettings, db_wrapper, timer, pogoWindowManager):
        MITMBase.__init__(self, args, id, last_known_state, websocket_handler, route_manager_daytime,
                          route_manager_nighttime, devicesettings, db_wrapper=db_wrapper, NoOcr=True, timer=timer,
                          mitm_mapper=mitm_mapper, pogoWindowManager=pogoWindowManager)

        # TODO: own InjectionSettings class
        self._injection_settings = {}
        self.__update_injection_settings()

    def __update_injection_settings(self):
        injected_settings = {}

        # don't try catch here, the injection settings update is called in the main loop anyway...
        routemanager = self._get_currently_valid_routemanager()
        if routemanager is None:
            # worker has to sleep, just empty out the settings...
            ids_iv = {}
            scanmode = "nothing"
        elif routemanager.mode == "mon_mitm":
            scanmode = "mons"
            ids_iv = routemanager.settings.get("mon_ids_iv", None)
        elif routemanager.mode == "raids_mitm":
            scanmode = "raids"
            ids_iv = routemanager.settings.get("mon_ids_iv", None)
        elif routemanager.mode == "iv_mitm" and isinstance(routemanager, RouteManagerIV):
            scanmode = "ivs"
            ids_iv = routemanager.encounter_ids_left
        else:
            # TODO: should we throw an exception here?
            ids_iv = {}
            scanmode = "nothing"
        injected_settings["scanmode"] = scanmode
        self._mitm_mapper.update_latest(origin=self._id, timestamp=int(time.time()), key="ids_iv",
                                        values_dict=ids_iv)
        self._mitm_mapper.update_latest(origin=self._id, timestamp=int(time.time()), key="injected_settings",
                                        values_dict=injected_settings)

    def _wait_data_worker(self, latest, proto_to_wait_for, timestamp):
        data_requested = None
        if latest is None:
            log.debug("Nothing received from %s since MAD started" % str(self._id))
            time.sleep(0.5)
        elif proto_to_wait_for not in latest:
            log.debug("No data linked to the requested proto since MAD started.")
            time.sleep(0.5)
        else:
            # proto has previously been received, let's check the timestamp...
            # TODO: int vs str-key?
            latest_proto = latest.get(proto_to_wait_for, None)

            try:
                current_routemanager = self._get_currently_valid_routemanager()
            except InternalStopWorkerException as e:
                log.info("Worker %s is to be stopped due to invalid routemanager/mode switch" % str(self._id))
                raise InternalStopWorkerException
            if current_routemanager is None:
                # we should be sleeping...
                log.warning("%s should be sleeping ;)" % str(self._id))
                return None
            current_mode = current_routemanager.mode
            latest_timestamp = latest_proto.get("timestamp", 0)
            if latest_timestamp >= timestamp:
                # TODO: consider reseting timestamp here since we clearly received SOMETHING
                latest_data = latest_proto.get("values", None)
                if latest_data is None:
                    time.sleep(0.5)
                    return None
                elif current_mode in ["mon_mitm", "iv_mitm"]:
                    # check if the GMO contains mons
                    for data_extract in latest_data['payload']['cells']:
                        for WP in data_extract['wild_pokemon']:
                            # TODO: teach Prio Q / Clusterer to hold additional data such as mon/encounter IDs
                            if WP['spawnpoint_id']:
                                data_requested = latest_data
                                break
                    if data_requested is None:
                        log.debug("No spawnpoints in data requested")
                        time.sleep(1)
                elif current_mode in ["raids_mitm"]:
                    for data_extract in latest_data['payload']['cells']:
                        for forts in data_extract['forts']:
                            if forts['id']:
                                data_requested = latest_data
                                break
                    if data_requested is None:
                        log.debug("No forts in data received")
                        time.sleep(0.5)
                else:
                    log.warning("No mode specified to wait for - this should not even happen...")
                    time.sleep(0.5)
            else:
                log.debug("latest timestamp of proto %s (%s) is older than %s"
                          % (str(proto_to_wait_for), str(latest_timestamp), str(timestamp)))
                # TODO: timeout error instead of data_error_counter? Differentiate timeout vs missing data (the
                # TODO: latter indicates too high speeds for example
                time.sleep(0.5)
        return data_requested
