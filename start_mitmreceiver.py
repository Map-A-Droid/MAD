import asyncio
import os
import sys
from asyncio import CancelledError, Task
from typing import Optional, Union

from aiohttp import web
from aioredis import Redis

from mapadroid.cache import NoopCache
from mapadroid.data_handler.MitmMapperClientConnector import \
    MitmMapperClientConnector
from mapadroid.db.DbFactory import DbFactory
from mapadroid.mad_apk import get_storage_obj
from mapadroid.mapping_manager.AbstractMappingManager import \
    AbstractMappingManager
from mapadroid.mapping_manager.MappingManagerClientConnector import \
    MappingManagerClientConnector
from mapadroid.mitm_receiver.MITMReceiver import MITMReceiver
from mapadroid.mitm_receiver.MitmDataProcessorManager import \
    MitmDataProcessorManager
from mapadroid.utils.EnvironmentUtil import setup_loggers, setup_runtime
from mapadroid.utils.SystemStatsUtil import get_system_infos
from mapadroid.utils.logging import (LoggerEnums, get_logger,
                                     init_logging)
from mapadroid.utils.madGlobals import application_args, terminate_mad
from mapadroid.utils.questGen import install_language

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

    setup_runtime()
    if application_args.config_mode and application_args.only_routes:
        logger.error('Unable to run with config_mode and only_routes.  Only use one option')
        sys.exit(1)
    if not application_args.only_scan and not application_args.only_routes:
        logger.error("No runmode selected. \nAllowed modes:\n"
                     " -os    ---- start scanner/devicecontroller\n"
                     " -or    ---- only calculate routes")
        sys.exit(1)
    # Elements that should initialized regardless of the functionality being used
    db_wrapper, db_exec = DbFactory.get_wrapper(application_args)
    await db_exec.setup()
    await db_wrapper.setup()

    mitm_mapper_connector = MitmMapperClientConnector()
    await mitm_mapper_connector.start()
    mitm_mapper = await mitm_mapper_connector.get_client()

    mitm_data_processor_manager = MitmDataProcessorManager(application_args, mitm_mapper, db_wrapper)
    await mitm_data_processor_manager.launch_processors()

    mapping_manager_connector = MappingManagerClientConnector()
    await mapping_manager_connector.start()
    mapping_manager: AbstractMappingManager = await mapping_manager_connector.get_client()

    storage_elem = await get_storage_obj(application_args, db_wrapper)

    mitm_receiver = MITMReceiver(mitm_mapper, application_args, mapping_manager, db_wrapper,
                                 storage_elem,
                                 mitm_data_processor_manager.get_queue(),
                                 enable_configmode=application_args.config_mode)

    mitm_receiver_task: web.AppRunner = await mitm_receiver.start()

    if application_args.statistic:
        logger.info("Starting statistics collector")
        loop = asyncio.get_running_loop()
        t_usage = loop.create_task(get_system_infos(db_wrapper))
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
            if mitm_mapper:
                await mitm_mapper_connector.close()
            if db_exec is not None:
                logger.debug("Calling db_pool_manager shutdown")
                cache: Union[Redis, NoopCache] = db_wrapper.get_cache()
                await cache.close()
                db_exec.shutdown()
        except Exception:
            logger.opt(exception=True).critical("An unhandled exception occurred during shutdown!")
        logger.info("Done shutting down")
        logger.debug(str(sys.exc_info()))
        sys.exit(exit_code)


if __name__ == "__main__":
    global application_args
    os.environ['LANGUAGE'] = application_args.language
    install_language()
    init_logging(application_args)
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
