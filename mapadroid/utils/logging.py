import logging
import os
import sys
from enum import IntEnum
from functools import wraps
from typing import Union

from loguru import logger


class LoggerEnums(IntEnum):
    unknown: int = 0
    system: int = 1
    database: int = 2
    madmin: int = 3
    patcher: int = 5
    websocket: int = 6
    webhook: int = 7
    ocr: int = 8
    routemanager: int = 9
    mitm: int = 10
    worker: int = 11
    utils: int = 12
    storage: int = 13
    package_mgr: int = 14
    plugin: int = 15
    asyncio: int = 16
    aiohttp_access: int = 17
    aiohttp_client: int = 18
    aiohttp_internal: int = 19
    aiohttp_server: int = 20
    aiohttp_web: int = 21
    aioredis: int = 22
    endpoint: int = 23
# ==================================
# ========== Core Logging ==========
# ==================================

def init_logging(args):
    log_level_label, log_level_val = log_level(args.log_level, args.verbose)
    _, log_file_level = log_level(args.log_file_level, args.verbose)
    log_trace = log_level_val <= 20
    log_file_trace = log_file_level <= 10
    colorize = not args.no_log_colors

    log_fmt_time_c = "[<cyan>{time:HH:mm:ss.SS}</cyan>]"
    log_fmt_time_fs = "[<cyan>{time:MM-DD HH:mm:ss.SS}</cyan>]"
    log_fmt_id = "[<cyan>{extra[name]: >17}</cyan>]"
    log_fmt_ip = "[<cyan>{extra[ip]: >17}</cyan>]"
    log_fmt_mod_c = "[<cyan>{module: >19.19}:{line: <4}</cyan>]"
    log_fmt_mod_fs = "[<cyan>{module: >19}:{line: <4}</cyan>]"
    log_fmt_level = "[<lvl>{level: >1.1}</lvl>]"
    log_fmt_msg = "<level>{message}</level>"

    log_format_c = [log_fmt_time_c, log_fmt_id, log_fmt_ip, log_fmt_mod_c, log_fmt_level, log_fmt_msg]
    log_format_fs = [log_fmt_time_fs, log_fmt_id, log_fmt_ip, log_fmt_mod_fs, log_fmt_level, log_fmt_msg]
    # Alter the logging capabilities based off the MAD launch settings
    if not args.no_file_logs:
        log_format_c[log_format_c.index(log_fmt_time_c)] = log_fmt_time_fs
        if not log_trace:
            log_format_c.remove(log_fmt_mod_c)
        else:
            log_format_c[log_format_c.index(log_fmt_mod_c)] = log_fmt_mod_fs
    fs_log_format = ' '.join(log_format_fs)
    log_format_console = ' '.join(log_format_c)
    logconfig = {
        #"levels": [
         #   {"name": "DEBUG2", "no": 9, "color": "<blue>"},
         #   {"name": "DEBUG3", "no": 8, "color": "<blue>"},
         #   {"name": "DEBUG4", "no": 7, "color": "<blue>"},
         #   {"name": "DEBUG5", "no": 6, "color": "<blue>"},
         #   {"name": "BAN", "no": 35, "color": "<yellow>"},
        #],
        "handlers": [
            {
                "sink": sys.stdout,
                "format": log_format_console,
                "colorize": colorize,
                "level": log_level_val,
                "enqueue": True,
                "filter": filter_errors
            },
            {
                "sink": sys.stderr,
                "format": log_format_console,
                "colorize": colorize,
                "level": "ERROR",
                "diagnose": log_trace,
                "backtrace": True,
                "enqueue": True
            }
        ],
        "extra": {"name": "Unknown", "ip": ""},
    }

    file_logs = [{
        "sink": os.path.join(args.log_path, "app" + ".log"),
        "format": fs_log_format,
        "level": log_file_level,
        "backtrace": True,
        "diagnose": log_file_trace,
        "enqueue": True,
        "encoding": "UTF-8",
        "filter": lambda record: True if record["extra"]["name"] in ("system", "Unknown", "asyncio",
                                                                     "endpoint") else False
        },
        {
            "sink": os.path.join(args.log_path, "app" + "_database.log"),
            "format": fs_log_format,
            "level": log_file_level,
            "backtrace": True,
            "diagnose": log_file_trace,
            "enqueue": True,
            "encoding": "UTF-8",
            "filter": lambda record: True if record["extra"]["name"] == "database" else False
        },
        {
            "sink": os.path.join(args.log_path, "app" + "_aiohttp.log"),
            "format": fs_log_format,
            "level": log_file_level,
            "backtrace": True,
            "diagnose": log_file_trace,
            "enqueue": True,
            "encoding": "UTF-8",
            "filter": lambda record: True if record["extra"]["name"] not in ("system", "Unknown", "asyncio",
                                                                             "database", "endpoint") else False
        }
    ]
    log_file_retention = str(args.log_file_retention) + " days"
    for log in file_logs:
        log["retention"] = log_file_retention
        log["rotation"] = str(args.log_file_rotation)
        log["compression"] = "zip"
    logconfig["handlers"].extend(file_logs)
    try:
        print("Logging will go to " + str(os.path.join(args.log_path, "app" + ".log")))
        logger.configure(**logconfig)
    except ValueError:
        logger.critical("Logging parameters/configuration is invalid.")
        sys.exit(1)
    try:
        init_custom(logger)
    except:
        pass
    logger.info("Setting log level to {} ({}).", str(log_level_val), log_level_label)


def log_level(arg_log_level, arg_debug_level):
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
        ("BAN", 35),
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
        return arg_log_level, forced_log_level

    # Default log level.
    if arg_debug_level == 0:
        return 'INFO', verbosity_map.get('INFO')

    # Log level based on count(-v) verbosity arguments.
    # Limit it to allowed grades, starting at DEBUG.
    debug_log_level_idx = next(key for key, (label, level) in enumerate(verbosity_levels) if label == 'DEBUG')

    # Limit custom verbosity to existing grades.
    debug_levels = verbosity_levels[:debug_log_level_idx + 1]
    debug_levels_length = len(debug_levels)

    if arg_debug_level < 0 or arg_debug_level > debug_levels_length:
        # Only show the message once per startup. This method is currently called once
        # for console logging, once for file logging.
        if not hasattr(log_level, 'bounds_exceeded'):
            logger.debug("Verbosity -v={} is outside of the bounds [0, {}]. Changed to nearest limit.",
                         str(arg_debug_level),
                         str(debug_levels_length))
            log_level.bounds_exceeded = True

        arg_debug_level = min(arg_debug_level, debug_levels_length)
        arg_debug_level = max(arg_debug_level, 0)

    # List goes from TRACE to DEBUG, -v=1=DEBUG is last index.
    # Note: List length is 1-based and so is count(-v).
    debug_level_idx = debug_levels_length - arg_debug_level
    debug_label, debug_level = debug_levels[debug_level_idx]
    return debug_label, debug_level


def apply_custom(func):
    @wraps(func)
    def decorated(self, *args, **kwargs):
        log = func(self, *args, **kwargs)
        try:
            init_custom(log)
        finally:
            return log
    return decorated


def init_custom(log_out: logger):
    log_out.level("DEBUG2", no=9, color="<blue>")
    log_out.level("DEBUG3", no=8, color="<blue>")
    log_out.level("DEBUG4", no=7, color="<blue>")
    log_out.level("DEBUG5", no=6, color="<blue>")
    log_out.level("BAN", no=35, color="<yellow>")
    log_out.debug2 = lambda message, *args, **kwargs: log_out.opt(depth=1).log("DEBUG2", message, *args, **kwargs)
    log_out.debug3 = lambda message, *args, **kwargs: log_out.opt(depth=1).log("DEBUG3", message, *args, **kwargs)
    log_out.debug4 = lambda message, *args, **kwargs: log_out.opt(depth=1).log("DEBUG4", message, *args, **kwargs)
    log_out.debug5 = lambda message, *args, **kwargs: log_out.opt(depth=1).log("DEBUG5", message, *args, **kwargs)
    log_out.ban = lambda message, *args, **kwargs: log_out.opt(depth=1).log("BAN", message, *args, **kwargs)


# ==================================
# ========== Filter Funcs ==========
# ==================================


def filter_errors(record):
    return record["level"] != "ERROR" and record["extra"]["name"] not in ("database")


# ==================================
# ========== Logger Inits ==========
# ==================================


def get_bind_name(logger_type: LoggerEnums, name: str) -> str:
    """ Translates the logger_type into the identifier for the log message.  Specifying name forces the identifier
        to that value
    """
    if name:
        return name
    elif logger_type == LoggerEnums.aiohttp_access:
        name = 'aiohttp_access'
    elif logger_type == LoggerEnums.database:
        name = 'database'
    elif logger_type == LoggerEnums.system:
        name = 'system'
    elif logger_type == LoggerEnums.aioredis:
        name = "aioredis"
    elif logger_type == LoggerEnums.asyncio:
        name = "asyncio"
    elif logger_type == LoggerEnums.aiohttp_client:
        name = "aiohttp_client"
    elif logger_type == LoggerEnums.aiohttp_web:
        name = "aiohttp_web"
    elif logger_type == LoggerEnums.aiohttp_server:
        name = "aiohttp_server"
    elif logger_type == LoggerEnums.aiohttp_internal:
        name = "aiohttp_internal"
    else:
        name = 'Unknown'
    return name


# ==================================
# ========= Custom Loggers =========
# ==================================
@apply_custom
def get_logger(logger_type: Union[LoggerEnums, int], name: str = None, filter_func: callable = None) -> logger:
    try:
        if isinstance(logger_type, LoggerEnums):
            log_id = logger_type
        elif logger_type.isdigit():
            log_id = LoggerEnums(logger_type)
        else:
            log_id = LoggerEnums.unknown
    except ValueError:
        log_id = LoggerEnums.unknown
    parsed_name = get_bind_name(log_id, name)
    new_logger = logger.bind(name=parsed_name)
    if filter_func:
        new_logger.patch(filter_func)
    return new_logger


# this is being used to intercept standard python logging to loguru
class InterceptHandler(logging.Handler):
    def __init__(self, *args, **kwargs):
        try:
            self.log_section = kwargs['log_section']
            del kwargs['log_section']
        except KeyError:
            self.log_section = LoggerEnums.unknown
        try:
            self.log_identifier = kwargs['log_identifier']
            del kwargs['log_identifier']
        except KeyError:
            self.log_identifier = LoggerEnums.unknown
        super().__init__(*args, **kwargs)
        self.log_identifier = get_bind_name(self.log_section, self.log_identifier)

    def emit(self, record):
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        with logger.contextualize(name=self.log_identifier):
            lvl: str = "DEBUG2"
            if self.log_section == LoggerEnums.database:
                lvl = "DEBUG"
            elif self.log_section == LoggerEnums.aiohttp_access:
                lvl = "DEBUG2"
            else:
                lvl = "DEBUG3"
            logger.opt(depth=depth, exception=record.exc_info).log(lvl, record.getMessage())


def get_origin_logger(existing_logger, origin=None) -> logger:
    """ Returns an origin logger.  Could be updated later to use ContextVar to allow for easier tracking of log
        messages
    """
    if not any([origin]):
        return existing_logger
    if origin:
        return get_logger(LoggerEnums.system, identifier=origin)


@apply_custom
def routelogger_set_origin(existing, origin=None) -> logger:
    if origin is None:
        return existing
    return existing.bind(origin=origin).patch(filter_route_with_origin)


def filter_route_with_origin(record):
    try:
        routename = record['extra']['identifier']
        record['extra']['identifier'] = record['extra']['origin']
        record['message'] = '{}: {}'.format(routename, record['message'])
    except KeyError:
        pass
