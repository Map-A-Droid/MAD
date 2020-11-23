import time
from datetime import datetime
from multiprocessing import Queue, Process
from mapadroid.db.DbPogoProtoSubmit import DbPogoProtoSubmit
from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.mitm_receiver.MitmMapper import MitmMapper
from mapadroid.utils.logging import get_logger, LoggerEnums, get_origin_logger

logger = get_logger(LoggerEnums.mitm)


class SerializedMitmDataProcessor(Process):
    def __init__(self, multi_proc_queue: Queue, application_args, mitm_mapper: MitmMapper,
                 db_wrapper: DbWrapper, name=None):
        Process.__init__(self, name=name)
        self.__queue: Queue = multi_proc_queue
        self.__db_submit: DbPogoProtoSubmit = db_wrapper.proto_submit
        self.__application_args = application_args
        self.__mitm_mapper: MitmMapper = mitm_mapper
        self.__name = name

    def run(self):
        logger.info("Starting serialized MITM data processor")
        while True:
            try:
                start_time = self.get_time_ms()
                item = self.__queue.get()
                if item is None:
                    logger.info("Received signal to stop MITM data processor")
                    break
                self.process_data(item[0], item[1], item[2])
                self.__queue.task_done()
                end_time = self.get_time_ms() - start_time
                logger.debug("MITM data processor {} finished queue item in {}ms", self.__name, end_time)
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt, stopping MITM data processor")
                break

    @logger.catch
    def process_data(self, received_timestamp, data, origin):
        origin_logger = get_origin_logger(logger, origin=origin)
        data_type = data.get("type", None)
        origin_logger.debug("Processing received data")
        processed_timestamp = datetime.fromtimestamp(received_timestamp)

        if data_type and not data.get("raw", False):
            self.__mitm_mapper.run_stats_collector(origin)

            origin_logger.debug4("Received data: {}", data)
            start_time = self.get_time_ms()
            if data_type == 106:
                origin_logger.info("Processing GMO. Received at {}", processed_timestamp)

                weather_time_start = self.get_time_ms()
                self.__db_submit.weather(origin, data["payload"], received_timestamp)
                weather_time = self.get_time_ms() - weather_time_start

                stops_time_start = self.get_time_ms()
                self.__db_submit.stops(origin, data["payload"])
                stops_time = self.get_time_ms() - stops_time_start

                gyms_time_start = self.get_time_ms()
                self.__db_submit.gyms(origin, data["payload"])
                gyms_time = self.get_time_ms() - gyms_time_start

                raids_time_start = self.get_time_ms()
                self.__db_submit.raids(origin, data["payload"], self.__mitm_mapper)
                raids_time = self.get_time_ms() - raids_time_start

                spawnpoints_time_start = self.get_time_ms()
                self.__db_submit.spawnpoints(origin, data["payload"], processed_timestamp)
                spawnpoints_time = self.get_time_ms() - spawnpoints_time_start

                mons_time_start = self.get_time_ms()
                self.__db_submit.mons(origin, received_timestamp, data["payload"], self.__mitm_mapper)
                mons_time = self.get_time_ms() - mons_time_start

                cells_time_start = self.get_time_ms()
                self.__db_submit.cells(origin, data["payload"])
                cells_time = self.get_time_ms() - cells_time_start

                gmo_loc_start = self.get_time_ms()
                self.__mitm_mapper.submit_gmo_for_location(origin, data["payload"])
                gmo_loc_time = self.get_time_ms() - gmo_loc_start

                full_time = self.get_time_ms() - start_time

                origin_logger.debug("Done processing GMO in {}ms (weather={}ms, stops={}ms, gyms={}ms, raids={}ms, " +
                                    "spawnpoints={}ms, mons={}ms, cells={}ms, gmo_loc={}ms)",
                                    full_time, weather_time, stops_time, gyms_time, raids_time,
                                    spawnpoints_time, mons_time, cells_time, gmo_loc_time)
            elif data_type == 102:
                playerlevel = self.__mitm_mapper.get_playerlevel(origin)
                if playerlevel >= 30:
                    origin_logger.debug("Processing encounter received at {}", processed_timestamp)
                    self.__db_submit.mon_iv(origin, received_timestamp, data["payload"], self.__mitm_mapper)
                    end_time = self.get_time_ms() - start_time
                    origin_logger.debug("Done processing encounter in {}ms", end_time)
                else:
                    origin_logger.warning("Playerlevel lower than 30 - not processing encounter IVs")
            elif data_type == 101:
                origin_logger.debug("Processing proto 101 (FORT_SEARCH)")
                self.__db_submit.quest(origin, data["payload"], self.__mitm_mapper)
                end_time = self.get_time_ms() - start_time
                origin_logger.debug("Done processing proto 101 in {}ms", end_time)
            elif data_type == 104:
                origin_logger.debug("Processing proto 104 (FORT_DETAILS)")
                self.__db_submit.stop_details(data["payload"])
                end_time = self.get_time_ms() - start_time
                origin_logger.debug("Done processing proto 104 in {}ms", end_time)
            elif data_type == 4:
                origin_logger.debug("Processing proto 4 (GET_HOLO_INVENTORY)")
                self.__mitm_mapper.generate_player_stats(origin, data["payload"])
                end_time = self.get_time_ms() - start_time
                origin_logger.debug("Done processing proto 4 in {}ms", end_time)
            elif data_type == 156:
                origin_logger.debug("Processing proto 156 (GYM_GET_INFO)")
                self.__db_submit.gym(origin, data["payload"])
                end_time = self.get_time_ms() - start_time
                origin_logger.debug("Done processing proto 156 in {}ms", end_time)

    @staticmethod
    def get_time_ms():
        return int(time.time() * 1000)
