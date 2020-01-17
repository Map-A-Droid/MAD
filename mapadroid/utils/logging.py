import logging
import os
import sys

from loguru import logger


def initLogging(args):
    log_level_label, log_level = logLevel(args.log_level, args.verbose)
    _, log_file_level = logLevel(args.log_file_level, args.verbose)
    log_trace = log_level <= 10
    log_file_trace = log_file_level <= 10
    colorize = not args.no_log_colors

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
                "colorize": colorize,
                "level": log_level,
                "enqueue": True,
                "filter": errorFilter
            },
            {
                "sink": sys.stderr,
                "format": "[<cyan>{time:MM-DD HH:mm:ss.SS}</cyan>] [<cyan>{thread.name: >17}</cyan>] [<cyan>{module: >19}:{line: <4}</cyan>] [<lvl>{level: >8}</lvl>] <level>{message}</level>",

                "colorize": colorize,
                "level": "ERROR",
                "diagnose": log_trace,
                "backtrace": True,
                "enqueue": True
            }
        ]
    }

    if not args.no_file_logs:
        file_logs = {
            "sink": os.path.join(args.log_path, args.log_filename),
            "format": "[{time:MM-DD HH:mm:ss.SS}] [{thread.name: >17}] [{module: >19}:{line: <4}] [{level: >8}] {message}",
            "level": log_file_level,
            "backtrace": True,
            "diagnose": log_file_trace,
            "enqueue": True,
            "encoding": "UTF-8"
        }

        if args.log_file_retention != 0:
            log_file_retention = str(args.log_file_retention) + " days"
            file_logs["retention"] = log_file_retention

        if str(args.log_file_rotation) != "0":
            file_logs["rotation"] = str(args.log_file_rotation)

        logconfig["handlers"].append(file_logs)

    try:
        logger.configure(**logconfig)
    except ValueError:
        logger.error("Logging parameters/configuration is invalid.")
        sys.exit(1)

    logger.info("Setting log level to {} ({}).", str(log_level), log_level_label)


def logLevel(arg_log_level, arg_debug_level):
    # List has an order, dict doesn't. We need the guaranteed order to
    # determine debug level based on arg_debug_level.
    verbosity_levels = [
        ("TRACE", 5),
        ("DEBUG5", 6),
        ("DEBUG4", 7),
        ("DEBUG3", 8),
        ("DEBUG2", 9),
        ("DEBUG", 10),
        ("INFO", 20),
        ("SUCCESS", 25),
        ("WARNING", 30),
        ("ERROR", 40),
        ("CRITICAL", 50)
    ]
    # Case insensitive.
    arg_log_level = arg_log_level.upper() if arg_log_level else None
    # Easy label->level lookup.
    verbosity_map = {k.upper(): v for k, v in verbosity_levels}

    # Log level by label.
    forced_log_level = verbosity_map.get(arg_log_level, None)
    if forced_log_level:
        return (arg_log_level, forced_log_level)

    # Default log level.
    if arg_debug_level == 0:
        return ('INFO', verbosity_map.get('INFO'))

    # Log level based on count(-v) verbosity arguments.
    # Limit it to allowed grades, starting at DEBUG.
    debug_log_level_idx = next(key for key, (label, level) in enumerate(verbosity_levels) if label == 'DEBUG')

    # Limit custom verbosity to existing grades.
    debug_levels = verbosity_levels[:debug_log_level_idx + 1]
    debug_levels_length = len(debug_levels)

    if arg_debug_level < 0 or arg_debug_level > debug_levels_length:
        # Only show the message once per startup. This method is currently called once
        # for console logging, once for file logging.
        if not hasattr(logLevel, 'bounds_exceeded'):
            logger.debug("Verbosity -v={} is outside of the bounds [0, {}]. Changed to nearest limit.",
                         str(arg_debug_level),
                         str(debug_levels_length))
            logLevel.bounds_exceeded = True

        arg_debug_level = min(arg_debug_level, debug_levels_length)
        arg_debug_level = max(arg_debug_level, 0)

    # List goes from TRACE to DEBUG, -v=1=DEBUG is last index.
    # Note: List length is 1-based and so is count(-v).
    debug_level_idx = debug_levels_length - arg_debug_level
    debug_label, debug_level = debug_levels[debug_level_idx]

    return (debug_label, debug_level)


def errorFilter(record):
    return record["level"] != "ERROR"


# this is being used to change log level for gevent/Flask/Werkzeug
class LogLevelChanger:
    def log(level, msg):
        if level >= 40:
            logger.log(level, msg)
        else:
            logger.opt(depth=6).log("DEBUG5", msg)


# this is being used to intercept standard python logging to loguru
class InterceptHandler(logging.Handler):
    def emit(self, record):
        logger.opt(depth=6, exception=record.exc_info).log("DEBUG5", record.getMessage())


logger.debug2 = lambda message, *args, **kwargs: logger.opt(depth=1).log("DEBUG2", message, *args, **kwargs)
logger.debug3 = lambda message, *args, **kwargs: logger.opt(depth=1).log("DEBUG3", message, *args, **kwargs)
logger.debug4 = lambda message, *args, **kwargs: logger.opt(depth=1).log("DEBUG4", message, *args, **kwargs)
logger.debug5 = lambda message, *args, **kwargs: logger.opt(depth=1).log("DEBUG5", message, *args, **kwargs)
