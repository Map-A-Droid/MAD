import asyncio
import functools
import logging
import os
import sys
from asyncio import Task

import pkg_resources

from mapadroid.utils.logging import get_logger, LoggerEnums, InterceptHandler
from mapadroid.utils.madGlobals import application_args

logger = get_logger(LoggerEnums.system)


def setup_runtime():
    check_dependencies()
    install_task_create_excepthook()
    create_folder(application_args.file_path)
    create_folder(application_args.upload_path)
    create_folder(application_args.temp_path)


def setup_loggers():
    logging.getLogger('asyncio').setLevel(logging.DEBUG)
    logging.getLogger('asyncio').addHandler(InterceptHandler(log_section=LoggerEnums.asyncio))
    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
    logging.getLogger('sqlalchemy.engine').addHandler(InterceptHandler(log_section=LoggerEnums.database))
    logging.getLogger('aiohttp.access').setLevel(logging.INFO)
    logging.getLogger('aiohttp.access').addHandler(InterceptHandler(log_section=LoggerEnums.aiohttp_access))
    logging.getLogger('aiohttp.client').setLevel(logging.INFO)
    logging.getLogger('aiohttp.client').addHandler(InterceptHandler(log_section=LoggerEnums.aiohttp_access))
    logging.getLogger('aiohttp.internal').setLevel(logging.INFO)
    logging.getLogger('aiohttp.internal').addHandler(InterceptHandler(log_section=LoggerEnums.aiohttp_access))
    logging.getLogger('aiohttp.server').setLevel(logging.INFO)
    logging.getLogger('aiohttp.server').addHandler(InterceptHandler(log_section=LoggerEnums.aiohttp_access))
    logging.getLogger('aiohttp.web').setLevel(logging.INFO)
    logging.getLogger('aiohttp.web').addHandler(InterceptHandler(log_section=LoggerEnums.aiohttp_access))


def create_folder(folder):
    if not os.path.exists(folder):
        logger.info(str(folder) + ' created')
        os.makedirs(folder)


def check_dependencies():
    with open("requirements.txt", "r") as f:
        deps = f.readlines()
        try:
            pkg_resources.require(deps)
        except pkg_resources.VersionConflict as version_error:
            logger.error("Some dependencies aren't met. Required: {} (Installed: {})", version_error.req,
                         version_error.dist)
            logger.error(
                "Most of the times you can fix it by running: pip3 install -r requirements.txt --upgrade")
            sys.exit(1)


# Patch to make exceptions in threads cause an exception.
def install_task_create_excepthook():
    """
    Workaround for sys.excepthook thread bug
    (https://sourceforge.net/tracker/?func=detail&atid=105470&aid=1230540&group_id=5470).
    Call once from __main__ before creating any threads.
    If using psyco, call psycho.cannotcompile(threading.Thread.run)
    since this replaces a new-style class method.
    """
    loop = asyncio.get_running_loop()
    create_task_old = loop.create_task

    def _handle_task_result(
            task: asyncio.Task,
            *,
            logger: logging.Logger,
    ) -> None:
        try:
            task.result()
        except asyncio.CancelledError as e:
            pass  # Task cancellation should not be logged as an error.
        except IndexError:
            pass  # We regularly throw index error in prioQ...
        # Ad the pylint ignore: we want to handle all exceptions here so that the result of the task
        # is properly logged. There is no point re-raising the exception in this callback.
        except Exception as e:  # pylint: disable=broad-except
            logger.debug2("Potential uncaught exception.", exc_info=True)
            logger.exception(e)
            raise e

    def create_task(*args, **kwargs) -> Task:
        try:
            task: Task = create_task_old(*args, **kwargs)
            task.add_done_callback(
                functools.partial(_handle_task_result, logger=logger)
            )
            return task
        except (KeyboardInterrupt, SystemExit) as e:
            raise e
        except BrokenPipeError:
            pass
        except Exception as inner_ex:
            logger.debug(inner_ex)
            raise inner_ex

    loop.create_task = create_task
