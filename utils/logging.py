import os
import sys
import logging

from loguru import logger


def initLogging(args):
    log_level = logLevel(args.log_level, args.verbose)
    log_file_level = logLevel(args.log_file_level, args.verbose)
    log_trace = log_level <= 10
    log_file_trace = log_file_level <= 10

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
            }
        ]
    }

    if not args.no_file_logs:
        file_logs = {
            "sink": os.path.join(args.log_path, args.log_filename),
            "format": "[{time:MM-DD HH:mm:ss.SS}] [{thread.name: >17}] [{module: >19}:{line: <4}] [{level: >8}] {message}",
            "level": log_file_level,
            "backtrace": log_file_trace,
            "enqueue": True,
            "encoding": "UTF-8"
        }

        if args.log_file_retention != 0:
            log_file_retention = str(args.log_file_retention) + " days"
            file_logs["retention"] = log_file_retention

        if args.log_file_rotation_size != 0:
            log_file_rotation_size = str(args.log_file_rotation_size) + " MB"
            file_logs["rotation"] = log_file_rotation_size

        logconfig["handlers"].append(file_logs)

    logger.configure(**logconfig)
    logger.info("Setting log level to {}", str(log_level))


def logLevel(arg_log_level, arg_debug_level):
    levelswitch = {
        "TRACE": 5,
        "DEBUG5": 6,
        "DEBUG4": 7,
        "DEBUG3": 8,
        "DEBUG2": 9,
        "DEBUG": 10,
        "INFO": 20,
        "SUCCESS": 25,
        "WARNING": 30,
        "ERROR": 40,
        "CRITICAL": 50
    }

    forced_log_level = levelswitch.get(arg_log_level, None)
    if forced_log_level:
        return forced_log_level

    if arg_debug_level == 0:
        return 20

    # DEBUG=10; starting with -v equals to args.verbose==1
    # starting with -vv equals to args.verbose==2 etc.
    loglevel = 11 - arg_debug_level
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
