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

    def run(self):
        logger.info("Starting serialized MITM data processor")
        while True:
            try:
                item = self.__queue.get()
                if item is None:
                    logger.info("Received signal to stop MITM data processor")
                    break
                self.process_data(item[0], item[1], item[2])
                self.__queue.task_done()
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt, stopping MITM data processor")
                break

    @logger.catch
    def process_data(self, received_timestamp, data, origin):
        origin_logger = get_origin_logger(logger, origin=origin)
        data_type = data.get("type", None)
        origin_logger.debug2("Processing received data")
        processed_timestamp = datetime.fromtimestamp(received_timestamp)

        if data_type and not data.get("raw", False):
            self.__mitm_mapper.run_stats_collector(origin)

            origin_logger.debug4("Received data: {}", data)
            if data_type == 106:
                # process GetMapObject
                origin_logger.info("Processing GMO received. Received at {}", processed_timestamp)

                self.__db_submit.weather(origin, data["payload"], received_timestamp)

                self.__db_submit.stops(origin, data["payload"])
                self.__db_submit.gyms(origin, data["payload"])
                self.__db_submit.raids(origin, data["payload"], self.__mitm_mapper)

                self.__db_submit.spawnpoints(origin, data["payload"], processed_timestamp)
                self.__db_submit.mons(origin, data["payload"], self.__mitm_mapper)
                self.__db_submit.cells(origin, data["payload"])
                self.__mitm_mapper.submit_gmo_for_location(origin, data["payload"])
                origin_logger.debug2("Done processing GMO")
            elif data_type == 102:
                playerlevel = self.__mitm_mapper.get_playerlevel(origin)
                if playerlevel >= 30:
                    origin_logger.debug("Processing encounter received at {}", processed_timestamp)
                    self.__db_submit.mon_iv(origin, received_timestamp, data["payload"], self.__mitm_mapper)
                    origin_logger.debug2("Done processing encounter")
                else:
                    origin_logger.warning("Playerlevel lower than 30 - not processing encounter IVs")
            elif data_type == 101:
                origin_logger.debug2("Processing proto 101")
                self.__db_submit.quest(origin, data["payload"], self.__mitm_mapper)
                origin_logger.debug2("Done processing proto 101")
            elif data_type == 104:
                origin_logger.debug2("Processing proto 104")
                self.__db_submit.stop_details(data["payload"])
                origin_logger.debug2("Done processing proto 104")
            elif data_type == 4:
                origin_logger.debug2("Processing proto 4")
                self.__mitm_mapper.generate_player_stats(origin, data["payload"])
                origin_logger.debug2("Done processing proto 4")
            elif data_type == 156:
                origin_logger.debug2("Processing proto 156")
                self.__db_submit.gym(origin, data["payload"])
                origin_logger.debug2("Done processing proto 156")
