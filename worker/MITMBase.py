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
            data_requested = self._wait_data_worker(latest, proto_to_wait_for, timestamp)

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
        
        
    @abstractmethod
    def _wait_data_worker(self, proto_to_wait_for, timestamp):
        """
        Wait_for_data for each worker
        :return:
        """
        pass
