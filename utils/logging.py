import os
import sys
import logging

from loguru import logger


def initLogging(args):
    log_level = logLevel(args.verbose)
    log_trace = log_level <= 10
    logconfig = {
        "levels": [
            {"name": "DEBUG2", "no": 9, "color": "<blue>"},
            {"name": "DEBUG3", "no": 8, "color": "<blue>"},
            {"name": "DEBUG4", "no": 7, "color": "<blue>"},
            {"name": "DEBUG5", "no": 6, "color": "<blue>"}
        ],
        "handlers": [
            {
                "sink": sys.stdout,
                "format": "[<cyan>{time:MM-DD HH:mm:ss.SS}</cyan>] [<cyan>{thread.name: >17}</cyan>] [<cyan>{module: >19}:{line: <4}</cyan>] [<lvl>{level: >8}</lvl>] <level>{message}</level>",
                "colorize": True,
                "level": log_level,
                "enqueue": True,
                "filter": errorFilter
            },
            {
                "sink": sys.stderr,
                "format": "[<cyan>{time:MM-DD HH:mm:ss.SS}</cyan>] [<cyan>{thread.name: >17}</cyan>] [<cyan>{module: >19}:{line: <4}</cyan>] [<lvl>{level: >8}</lvl>] <level>{message}</level>",
                "colorize": True,
                "level": "ERROR",
                "backtrace": log_trace,
                "enqueue": True
            },
            {
                "sink": os.path.join(args.log_path, args.log_filename),
                "format": "[{time:MM-DD HH:mm:ss.SS}] [{thread.name: >17}] [{module: >19}:{line: <4}] [{level: >8}] {message}",
                "level": log_level,
                "backtrace": log_trace,
                "rotation": "0:00",
                "compression": "zip",
                "retention": "10 days",
                "enqueue": True,
                "encoding": "UTF-8"
            }
        ]
    }

    logger.configure(**logconfig)
    logger.info("Setting log level to {}", str(log_level))


def logLevel(debug_level):
    if debug_level == 0:
        return 20

    # DEBUG=10; starting with -v equals to args.verbose==1
    # starting with -vv equals to args.verbose==2 etc.
    loglevel = 11 - debug_level
    return loglevel


def errorFilter(record):
    return record["level"] != "ERROR"


# this is being used to change log level for gevent/Flask/Werkzeug
class LogLevelChanger:
    def log(level, msg):
        logger.opt(depth=6).log("DEBUG5", msg)


# this is being used to intercept standard python logging to loguru
class InterceptHandler(logging.Handler):
    def emit(self, record):
        logger.opt(depth=6, exception=record.exc_info).log("DEBUG5", record.getMessage())


def debug2(message, *args, **kwargs):
    logger.opt(depth=1).log("DEBUG2", message, *args, **kwargs)


def debug3(message, *args, **kwargs):
    logger.opt(depth=1).log("DEBUG3", message, *args, **kwargs)


def debug4(message, *args, **kwargs):
    logger.opt(depth=1).log("DEBUG4", message, *args, **kwargs)


def debug5(message, *args, **kwargs):
    logger.opt(depth=1).log("DEBUG5", message, *args, **kwargs)


logger.debug2 = debug2
logger.debug3 = debug3
logger.debug4 = debug4
logger.debug5 = debug5
