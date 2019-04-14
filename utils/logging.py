import sys
from loguru import logger
import os


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
                "sink": sys.stderr,
                "format": "[<cyan>{time:MM-DD HH:mm:ss.SS}</cyan>] [<cyan>{thread.name: >17}</cyan>] [<cyan>{module: >19}:{line: <4}</cyan>] [<lvl>{level: >8}</lvl>] <level>{message}</level>",
                "colorize": True,
                "level": log_level,
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


class MadLoggerUtils:
    # this is being used to change log level for gevent/Flask/Werkzeug
    def log(level, msg):
        logger.log("DEBUG5", msg)
