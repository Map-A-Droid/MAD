import asyncio
import calendar
import datetime
import functools
import gc
import linecache
import logging
import os
import sys
from asyncio import CancelledError, Task
from threading import active_count
from typing import Any, Optional, Tuple

import pkg_resources
import psutil

from mapadroid.data_handler.MitmMapperServer import MitmMapperServer
from mapadroid.db.DbFactory import DbFactory
from mapadroid.db.helper.TrsUsageHelper import TrsUsageHelper
from mapadroid.utils.EnvironmentUtil import setup_loggers, setup_runtime
from mapadroid.utils.SystemStatsUtil import get_system_infos
from mapadroid.utils.logging import (InterceptHandler, LoggerEnums, get_logger,
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

    mitm_mapper = MitmMapperServer(db_wrapper)
    await mitm_mapper.start()

    if application_args.statistic:
        logger.info("Starting statistics collector")
        loop = asyncio.get_running_loop()
        t_usage = loop.create_task(get_system_infos(db_wrapper))
    logger.info("MAD is now running.....")
    exit_code = 0
    try:
        if application_args.unit_tests:
            pass
            # from mapadroid.tests.local_api import LocalAPI
            # api_ready = False
            # api = LocalAPI()
            # logger.info('Checking API status')
            # if not data_manager.get_root_resource('device').keys():
            #     from mapadroid.tests.test_utils import ResourceCreator
            #     logger.info('Creating a device')
            #     device_creator = ResourceCreator(api, prefix='MADCore')
            #     res = device_creator.create_valid_resource('device')[0]
            #     mapping_manager.update()
            # max_attempts = 30
            # attempt = 0
            # while not api_ready and attempt < max_attempts:
            #     try:
            #         api.get('/api')
            #         api_ready = True
            #         logger.info('API is ready for unit testing')
            #     except Exception:
            #         attempt += 1
            #         time.sleep(1)
            # if api_ready:
            #     loader = unittest.TestLoader()
            #     start_dir = 'mapadroid/tests/'
            #     suite = loader.discover(start_dir)
            #     runner = unittest.TextTestRunner()
            #     result = runner.run(suite)
            #     exit_code = 0 if result.wasSuccessful() else 1
            #     raise KeyboardInterrupt
            # else:
            #     exit_code = 1
        else:
            while True:
                await asyncio.sleep(10)
    except (KeyboardInterrupt, CancelledError):
        logger.info("Shutdown signal received")
    finally:
        try:
            logger.success("Stop called")
            terminate_mad.set()
            # now cleanup all threads...
            if t_usage:
                t_usage.cancel()
            if mitm_mapper:
                await mitm_mapper.shutdown()
            if db_exec is not None:
                logger.debug("Calling db_pool_manager shutdown")
                # db_exec.shutdown()
                logger.debug("Done shutting down db_pool_manager")
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
