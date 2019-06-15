from multiprocessing import Queue, Process
from datetime import datetime

from db.DbFactory import DbFactory
from db.dbWrapperBase import DbWrapperBase
from mitm_receiver.MitmMapper import MitmMapper
from utils.logging import logger


class MitmDataProcessor(Process):
    def __init__(self, multi_proc_queue: Queue, application_args, mitm_mapper: MitmMapper, db_wrapper, name=None):
        Process.__init__(self, name=name)
        self.__queue: Queue = multi_proc_queue
        self.__db_wrapper: DbWrapperBase = db_wrapper
        self.__application_args = application_args
        self.__mitm_mapper: MitmMapper = mitm_mapper

    def run(self):
        # build a private DbWrapper instance...
        logger.info("Starting MITMDataProcessor")
        while True:
            try:
                item = self.__queue.get()

                try:
                    items_left = self.__queue.qsize()
                except NotImplementedError:
                    items_left = 0

                logger.debug(
                    "MITM data processing worker retrieved data. Queue length left afterwards: {}", str(items_left))
                if items_left > 50:
                    logger.warning(
                        "MITM data processing workers are falling behind! Queue length: {}", str(items_left))

                if item is None:
                    logger.warning("Received none from queue of data")
                    break
                self.process_data(item[0], item[1], item[2])
                self.__queue.task_done()
            except KeyboardInterrupt as e:
                logger.info("MITMDataProcessor received keyboard interrupt, stopping")
                break

    @logger.catch
    def process_data(self, received_timestamp, data, origin):

        type = data.get("type", None)
        raw = data.get("raw", False)

        if raw:
            logger.debug5("Received raw payload: {}", data["payload"])

        if type and not raw:
            self.__mitm_mapper.run_stats_collector(origin)

            logger.debug4("Received payload: {}", data["payload"])

            if type == 106:
                # process GetMapObject
                logger.success("Processing GMO received from {}. Received at {}", str(
                    origin), str(datetime.fromtimestamp(received_timestamp)))

                if self.__application_args.weather:
                    self.__db_wrapper.submit_weather_map_proto(
                        origin, data["payload"], received_timestamp)

                self.__db_wrapper.submit_pokestops_map_proto(
                    origin, data["payload"])
                self.__db_wrapper.submit_gyms_map_proto(origin, data["payload"])
                self.__db_wrapper.submit_raids_map_proto(
                    origin, data["payload"], self.__mitm_mapper)

                self.__db_wrapper.submit_spawnpoints_map_proto(
                    origin, data["payload"])
                mon_ids_iv = self.__mitm_mapper.get_mon_ids_iv(origin)
                self.__db_wrapper.submit_mons_map_proto(
                    origin, data["payload"], mon_ids_iv, self.__mitm_mapper)
                self.__db_wrapper.submit_nearby_map_proto(origin, data["payload"])
            elif type == 102:
                playerlevel = self.__mitm_mapper.get_playerlevel(origin)
                if playerlevel >= 30:
                    logger.info("Processing Encounter received from {} at {}", str(
                        origin), str(received_timestamp))
                    self.__db_wrapper.submit_mon_iv(
                        origin, received_timestamp, data["payload"], self.__mitm_mapper)
                else:
                    logger.debug(
                        'Playerlevel lower than 30 - not processing encounter Data')
            elif type == 101:
                self.__db_wrapper.submit_quest_proto(origin, data["payload"], self.__mitm_mapper)
            elif type == 104:
                self.__db_wrapper.submit_pokestops_details_map_proto(
                    data["payload"])
            elif type == 4:
                self.__mitm_mapper.generate_player_stats(origin, data["payload"])
