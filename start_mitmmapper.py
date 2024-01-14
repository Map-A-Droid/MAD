import asyncio
import os
import sys
from asyncio import CancelledError, Task
from typing import Optional

from mapadroid.data_handler.grpc.MitmMapperServer import MitmMapperServer
from mapadroid.db.DbFactory import DbFactory
from mapadroid.utils.EnvironmentUtil import setup_loggers, setup_runtime
from mapadroid.utils.logging import LoggerEnums, get_logger, init_logging
from mapadroid.utils.madGlobals import MadGlobals, terminate_mad
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

    mitm_mapper = MitmMapperServer()
    await mitm_mapper.start()

    if MadGlobals.application_args.statistic:
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
    MadGlobals.load_args()
    os.environ['LANGUAGE'] = MadGlobals.application_args.language
    init_logging(MadGlobals.application_args)
    setup_loggers()
    logger = get_logger(LoggerEnums.system)

    try:
        asyncio.run(start(), debug=True)
    except (KeyboardInterrupt, Exception) as e:
        logger.info(f"Shutting down. {e}")
        logger.exception(e)
