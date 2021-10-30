import grpc
from grpc._cython.cygrpc import CompressionAlgorithm, CompressionLevel

from mapadroid.data_handler.stats.StatsHandler import StatsHandler
from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.grpc.compiled.stats_handler.stats_handler_pb2 import Stats
from mapadroid.grpc.compiled.shared.Ack_pb2 import Ack
from mapadroid.grpc.stubs.stats_handler.stats_handler_pb2_grpc import StatsHandlerServicer, \
    add_StatsHandlerServicer_to_server
from mapadroid.utils.collections import Location
from mapadroid.utils.DatetimeWrapper import DatetimeWrapper
from mapadroid.utils.logging import LoggerEnums, get_logger
from mapadroid.utils.madGlobals import (MonSeenTypes, PositionType,
                                        TransportType, application_args)
from mapadroid.worker.WorkerType import WorkerType

logger = get_logger(LoggerEnums.stats_handler)


class StatsHandlerServer(StatsHandlerServicer, StatsHandler):
    def __init__(self, db_wrapper: DbWrapper):
        StatsHandler.__init__(self, db_wrapper=db_wrapper)
        self.__server = None

    async def start(self):
        await StatsHandler.start(self)
        max_message_length = 100 * 1024 * 1024
        options = [('grpc.max_message_length', max_message_length),
                   ('grpc.max_receive_message_length', max_message_length)]
        if application_args.statshandler_compression:
            options.extend([('grpc.default_compression_algorithm', CompressionAlgorithm.gzip),
                            ('grpc.grpc.default_compression_level', CompressionLevel.medium)])
        self.__server = grpc.aio.server(options=options)
        add_StatsHandlerServicer_to_server(self, self.__server)
        address = f'{application_args.statshandler_ip}:{application_args.statshandler_port}'

        if application_args.statshandler_tls_cert_file and application_args.statshandler_tls_private_key_file:
            await self.__secure_port(address)
        else:
            await self.__insecure_port(address)
            logger.warning("Insecure StatsHandler gRPC API server")

        logger.info("Starting server on %s", address)
        await self.__server.start()

    async def __secure_port(self, address):
        with open(application_args.statshandler_tls_private_key_file, 'r') as keyfile, open(application_args.statshandler_tls_cert_file, 'r') as certfile:
            private_key = keyfile.read()
            certificate_chain = certfile.read()
        credentials = grpc.ssl_server_credentials(
            [(private_key, certificate_chain)]
        )
        self.__server.add_secure_port(address, credentials)

    async def __insecure_port(self, address):
        self.__server.add_insecure_port(address)

    async def shutdown(self):
        await StatsHandler.shutdown(self)
        if self.__server:
            await self.__server.stop(0)

    async def StatsCollect(self, request: Stats, context: grpc.aio.ServicerContext) -> Ack:
        logger.debug("StatsCollect called")
        # depending on the data_to_collect we need to parse fields..
        if request.HasField("wild_mons"):
            await self.stats_collect_wild_mon(
                request.worker.name, encounter_ids=request.wild_mons.encounter_ids,
                time_scanned=DatetimeWrapper.fromtimestamp(request.timestamp))
        elif request.HasField("mon_iv"):
            await self.stats_collect_mon_iv(
                request.worker.name, encounter_id=request.mon_iv.encounter_id,
                is_shiny=request.mon_iv.is_shiny,
                time_scanned=DatetimeWrapper.fromtimestamp(request.timestamp))
        elif request.HasField("quest"):
            await self.stats_collect_quest(
                request.worker.name,
                time_scanned=DatetimeWrapper.fromtimestamp(request.timestamp))
        elif request.HasField("raid"):
            await self.stats_collect_raid(
                request.worker.name,
                time_scanned=DatetimeWrapper.fromtimestamp(request.timestamp),
                amount_raids=request.raid.amount)
        elif request.HasField("location_data"):
            if not request.location_data.HasField("location"):
                # TODO: Ack failure indicator?
                return Ack()
            location = Location(request.location_data.location.latitude,
                                request.location_data.location.longitude)
            await self.stats_collect_location_data(
                request.worker.name,
                location=location,
                success=request.location_data.success,
                fix_timestamp=request.location_data.fix_timestamp,
                data_timestamp=request.location_data.data_timestamp,
                # TODO: Probably gotta read value of protobuf enum...
                position_type=PositionType(request.location_data.position_type),
                worker_type=WorkerType(request.location_data.walker),
                transport_type=TransportType(request.location_data.transport_type),
                timestamp_of_record=request.timestamp)
        elif request.HasField("seen_type"):
            await self.stats_collect_seen_type(
                encounter_ids=request.seen_type.encounter_ids,
                type_of_detection=MonSeenTypes(request.seen_type.type_of_detection),
                time_of_scan=DatetimeWrapper.fromtimestamp(request.timestamp))
        return Ack()
