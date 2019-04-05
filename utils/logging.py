from loguru import logger


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
