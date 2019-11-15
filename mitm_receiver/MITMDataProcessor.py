from multiprocessing import Queue, Process
from datetime import datetime

from db.DbWrapper import DbWrapper
from db.DbPogoProtoSubmit import DbPogoProtoSubmit
from mitm_receiver.MitmMapper import MitmMapper
from utils.logging import logger


class MitmDataProcessor(Process):
    def __init__(self, multi_proc_queue: Queue, application_args, mitm_mapper: MitmMapper,
                 db_wrapper: DbWrapper, name=None):
        Process.__init__(self, name=name)
        self.__queue: Queue = multi_proc_queue
        self.__db_submit: DbPogoProtoSubmit = db_wrapper.proto_submit
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

    def get_queue_items(self):
        try:
            items_left = self.__queue.qsize()
        except NotImplementedError:
            items_left = 0
        return items_left

    @logger.catch
    def process_data(self, received_timestamp, data, origin):

        type = data.get("type", None)
        raw = data.get("raw", False)
        logger.debug2("Processing data of {}".format(origin))
        if raw:
            logger.debug5("Received raw payload: {}", data["payload"])

        if type and not raw:
            logger.debug2("Running stats collector of {}".format(origin))
            if self.__application_args.game_stats:
                self.__mitm_mapper.run_stats_collector(origin)

            logger.debug4("Received payload: {}", data["payload"])
            if type == 106:
                # process GetMapObject
                logger.success("Processing GMO received from {}. Received at {}", str(
                    origin), str(datetime.fromtimestamp(received_timestamp)))

                if self.__application_args.weather:
                    self.__db_submit.weather(origin, data["payload"], received_timestamp)

                self.__db_submit.stops(origin, data["payload"])
                self.__db_submit.gyms(origin, data["payload"])
                self.__db_submit.raids(origin, data["payload"], self.__mitm_mapper)

                self.__db_submit.spawnpoints(origin, data["payload"])
                mon_ids_iv = self.__mitm_mapper.get_mon_ids_iv(origin)
                self.__db_submit.mons(origin, data["payload"], mon_ids_iv, self.__mitm_mapper)
                self.__db_submit.cells(origin, data["payload"])
                self.__mitm_mapper.submit_gmo_for_location(origin, data["payload"])
                logger.debug2("Done processing GMO of {}".format(origin))
            elif type == 102:
                playerlevel = self.__mitm_mapper.get_playerlevel(origin)
                if playerlevel >= 30:
                    logger.info("Processing Encounter received from {} at {}", str(origin), str(received_timestamp))
                    self.__db_submit.mon_iv(origin, received_timestamp, data["payload"], self.__mitm_mapper)
                    logger.debug2("Done processing encounter of {}".format(origin))
                else:
                    logger.debug('Playerlevel lower than 30 - not processing encounter Data')
            elif type == 101:
                logger.debug2("Processing proto 101 of {}".format(origin))
                self.__db_submit.quest(origin, data["payload"], self.__mitm_mapper)
                logger.debug2("Done processing proto 101 of {}".format(origin))
            elif type == 104:
                logger.debug2("Processing proto 104 of {}".format(origin))
                self.__db_submit.stop_details(data["payload"])
                logger.debug2("Done processing proto 104 of {}".format(origin))
            elif type == 4:
                logger.debug2("Processing proto 4 of {}".format(origin))
                self.__mitm_mapper.generate_player_stats(origin, data["payload"])
                logger.debug2("Done processing proto 4 of {}".format(origin))
            elif type == 156:
                logger.debug2("Processing proto 156 of {}".format(origin))
                self.__db_submit.gym(origin, data["payload"])
                logger.debug2("Done processing proto 156 of {}".format(origin))
