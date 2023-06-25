import asyncio
import os
import sys
from asyncio import CancelledError, Task
from typing import Optional

from aiohttp import web
from redis import Redis

from mapadroid.account_handler import setup_account_handler
from mapadroid.account_handler.AbstractAccountHandler import \
    AbstractAccountHandler
from mapadroid.data_handler.grpc.MitmMapperClient import MitmMapperClient
from mapadroid.data_handler.grpc.MitmMapperClientConnector import \
    MitmMapperClientConnector
from mapadroid.data_handler.grpc.StatsHandlerClient import StatsHandlerClient
from mapadroid.data_handler.grpc.StatsHandlerClientConnector import \
    StatsHandlerClientConnector
from mapadroid.data_handler.mitm_data.MitmMapperType import MitmMapperType
from mapadroid.data_handler.mitm_data.RedisMitmMapper import RedisMitmMapper
from mapadroid.db.DbFactory import DbFactory
from mapadroid.mad_apk import get_storage_obj
from mapadroid.mapping_manager.AbstractMappingManager import \
    AbstractMappingManager
from mapadroid.mapping_manager.MappingManagerClientConnector import \
    MappingManagerClientConnector
from mapadroid.mitm_receiver.data_processing.InProcessMitmDataProcessorManager import \
    InProcessMitmDataProcessorManager
from mapadroid.mitm_receiver.MITMReceiver import MITMReceiver
from mapadroid.utils.EnvironmentUtil import setup_loggers, setup_runtime
from mapadroid.utils.logging import LoggerEnums, get_logger, init_logging
from mapadroid.utils.madGlobals import MadGlobals, terminate_mad
from mapadroid.utils.questGen import QuestGen
from mapadroid.utils.redisReport import report_queue_size
from mapadroid.utils.SystemStatsUtil import get_system_infos

try:
    import uvloop

    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    uvloop.install()
except Exception as e:
    # uvloop is optional
    pass

py_version = sys.version_info
if py_version.major < 3 or (py_version.major == 3 and py_version.minor < 9):
    print("MAD requires at least python 3.9! Your version: {}.{}"
          .format(py_version.major, py_version.minor))
    sys.exit(1)


async def start():
    t_usage: Optional[Task] = None
    t_reporting: Optional[Task] = None
    mitm_mapper_connector: Optional[MitmMapperClientConnector] = None
    setup_runtime()
    if MadGlobals.application_args.config_mode and MadGlobals.application_args.only_routes:
        logger.error('Unable to run with config_mode and only_routes.  Only use one option')
        sys.exit(1)
    if not MadGlobals.application_args.only_scan and not MadGlobals.application_args.only_routes:
        logger.error("No runmode selected. \nAllowed modes:\n"
                     " -os    ---- start scanner/devicecontroller\n"
                     " -or    ---- only calculate routes")
        sys.exit(1)
    # Elements that should initialized regardless of the functionality being used
    db_wrapper, db_exec = await DbFactory.get_wrapper(MadGlobals.application_args)

    if MadGlobals.application_args.mitmmapper_type == MitmMapperType.grpc:
        mitm_mapper_connector = MitmMapperClientConnector()
        await mitm_mapper_connector.start()
        mitm_mapper: MitmMapperClient = await mitm_mapper_connector.get_client()
    elif MadGlobals.application_args.mitmmapper_type == MitmMapperType.redis:
        mitm_mapper: RedisMitmMapper = RedisMitmMapper(db_wrapper)
        await mitm_mapper.start()
    else:
        logger.critical("Unsupported MitmMapper type for multi-host/process setup {}", MadGlobals.application_args.mitmmapper_type)
        sys.exit(1)

    stats_handler_connector = StatsHandlerClientConnector()
    await stats_handler_connector.start()
    stats_handler: StatsHandlerClient = await stats_handler_connector.get_client()
    await stats_handler.start()

    quest_gen: QuestGen = QuestGen()
    await quest_gen.setup()
    account_handler: AbstractAccountHandler = await setup_account_handler(db_wrapper)

    mitm_data_processor_manager = InProcessMitmDataProcessorManager(mitm_mapper, stats_handler, db_wrapper, quest_gen,
                                                                    account_handler=account_handler)
    await mitm_data_processor_manager.launch_processors()

    mapping_manager_connector = MappingManagerClientConnector()
    await mapping_manager_connector.start()
    mapping_manager: AbstractMappingManager = await mapping_manager_connector.get_client()

    storage_elem = await get_storage_obj(db_wrapper)

    mitm_receiver = MITMReceiver(mitm_mapper, mapping_manager, db_wrapper,
                                 storage_elem,
                                 mitm_data_processor_manager.get_queue(),
                                 account_handler=account_handler)

    mitm_receiver_task: web.AppRunner = await mitm_receiver.start()

    if MadGlobals.application_args.statistic:
        logger.info("Starting statistics collector")
        loop = asyncio.get_running_loop()
        t_usage = loop.create_task(get_system_infos(db_wrapper))
    if MadGlobals.application_args.redis_report_queue_key:
        logger.info("Starting report queue size to Redis via key: {}", MadGlobals.application_args.redis_report_queue_key)
        loop = asyncio.get_running_loop()
        t_reporting = loop.create_task(report_queue_size(db_wrapper, mitm_data_processor_manager.get_queue()))
    logger.info("MAD is now running.....")
    exit_code = 0
    try:
        while True:
            await asyncio.sleep(10)
    except (KeyboardInterrupt, CancelledError):
        logger.info("Shutdown signal received")
    finally:
        await mitm_receiver_task.shutdown()
        await mitm_receiver.shutdown()
        await storage_elem.shutdown()
        try:
            logger.success("Stop called")
            terminate_mad.set()
            # now cleanup all threads...
            if t_usage:
                t_usage.cancel()
            if t_reporting:
                t_reporting.cancel()
            if mitm_mapper_connector:
                await mitm_mapper_connector.close()
            if db_exec is not None:
                logger.debug("Calling db_pool_manager shutdown")
                cache: Redis = await db_wrapper.get_cache()
                await cache.close()
                await db_exec.shutdown()
        except Exception:
            logger.opt(exception=True).critical("An unhandled exception occurred during shutdown!")
        logger.info("Done shutting down")
        logger.debug(str(sys.exc_info()))
        sys.exit(exit_code)


if __name__ == "__main__":
    MadGlobals.load_args()
    os.environ['LANGUAGE'] = MadGlobals.application_args.language
    init_logging(MadGlobals.application_args)
    setup_loggers()
    logger = get_logger(LoggerEnums.system)

    loop = asyncio.get_event_loop()
    # signal.signal(signal.SIGINT, signal_handler)
    # signal.signal(signal.SIGTERM, signal_handler)

    loop_being_run = loop
    try:
        # loop.run_until_complete(start())
        asyncio.run(start(), debug=True)
    except (KeyboardInterrupt, Exception) as e:
        # shutdown(loop_being_run)
        logger.info(f"Shutting down. {e}")
        logger.exception(e)
