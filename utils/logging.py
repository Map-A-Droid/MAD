from loguru import logger


class MadLoggerUtils:
    # thisis being used to change log level for gevent/Flask/Werkzeug
    def log(level, msg):
        logger.log("DEBUG", msg)
