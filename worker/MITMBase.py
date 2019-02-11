import logging
import math
import time
import datetime

from route.RouteManagerIV import RouteManagerIV
from utils.geo import get_distance_of_two_points_in_meters
from utils.madGlobals import InternalStopWorkerException
from worker.WorkerBase import WorkerBase
from abc import ABC, abstractmethod

log = logging.getLogger(__name__)


class MITMBase(WorkerBase):
    def __init__(self, args, id, last_known_state, websocket_handler, route_manager_daytime,
                 route_manager_nighttime, devicesettings, db_wrapper, timer, NoOcr=False):
        WorkerBase.__init__(self, args, id, last_known_state, websocket_handler, route_manager_daytime,
                            route_manager_nighttime, devicesettings, db_wrapper=db_wrapper, NoOcr=True, timer=timer)
                            
                            
    def _wait_for_data(self, timestamp, proto_to_wait_for=106):
        timeout = self._devicesettings.get("mitm_wait_timeout", 45)
        max_data_err_counter = self._devicesettings.get("max_data_err_counter", 60)

        log.info('Waiting for data after %s, error count is at %s' % (str(timestamp), str(self._data_error_counter)))
        data_requested = None

        while (data_requested is None and timestamp + timeout >= math.floor(time.time())
               and self._data_error_counter < max_data_err_counter):
            latest = self._mitm_mapper.request_latest(self._id)
            if latest is None:
                log.debug("Nothing received from %s since MAD started" % str(self._id))
                time.sleep(0.5)
                continue
            elif proto_to_wait_for not in latest:
                log.debug("No data linked to the requested proto since MAD started. Count: %s"
                          % str(self._data_error_counter))
                self._data_error_counter += 1
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
                        self._data_error_counter += 1
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
                            self._data_error_counter += 1
                            time.sleep(1)
                    elif current_mode in ["raids_mitm"]:
                        for data_extract in latest_data['payload']['cells']:
                            for forts in data_extract['forts']:
                                if forts['id']:
                                    data_requested = latest_data
                                    break
                        if data_requested is None:
                            log.debug("No forts in data received")
                            self._data_error_counter += 1
                            time.sleep(0.5)
                    else:
                        log.warning("No mode specified to wait for - this should not even happen...")
                        self._data_error_counter += 1
                        time.sleep(0.5)
                else:
                    log.debug("latest timestamp of proto %s (%s) is older than %s"
                              % (str(proto_to_wait_for), str(latest_timestamp), str(timestamp)))
                    # TODO: timeout error instead of data_error_counter? Differentiate timeout vs missing data (the
                    # TODO: latter indicates too high speeds for example
                    self._data_error_counter += 1
                    time.sleep(0.5)

        if data_requested is not None:
            log.info('Got the data requested...')
            self._reboot_count = 0
            self._restart_count = 0
            self._data_error_counter = 0
            self._rec_data_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            # TODO: timeout also happens if there is no useful data such as mons nearby in mon_mitm mode, we need to
            # TODO: be more precise (timeout vs empty data)
            log.warning("Timeout waiting for data")
            try:
                current_routemanager = self._get_currently_valid_routemanager()
            except InternalStopWorkerException as e:
                log.info("Worker %s is to be stopped due to invalid routemanager/mode switch" % str(self._id))
                raise InternalStopWorkerException
            self._reboot_count += 1
            self._restart_count += 1
            if (self._devicesettings.get("reboot", False)
                    and self._reboot_count > self._devicesettings.get("reboot_thresh", 5)
                    and not current_routemanager.init):
                log.error("Rebooting %s" % str(self._id))
                self._reboot()
                raise InternalStopWorkerException
            elif self._data_error_counter >= max_data_err_counter and self._restart_count > 5:
                self._data_error_counter = 0
                self._restart_count = 0
                self._restart_pogo(True)
            elif self._data_error_counter >= max_data_err_counter and self._restart_count <= 5:
                self._data_error_counter = 0
        return data_requested
        
