import sys

from db.dbWrapperBase import DbWrapperBase
from db.monocleWrapper import MonocleWrapper
from db.rmWrapper import RmWrapper
from utils.logging import logger


class DbFactory:
    @staticmethod
    def get_wrapper(args) -> DbWrapperBase:
        if args.db_method == "rm":
            return RmWrapper(args)
        elif args.db_method == "monocle":
            return MonocleWrapper(args)
        else:
            logger.error("Invalid db_method in config. Exiting")
            sys.exit(1)