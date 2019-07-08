import sys
from multiprocessing.managers import SyncManager

from db.dbWrapperBase import DbWrapperBase
from db.monocleWrapper import MonocleWrapper, MonocleWrapperManager
from db.rmWrapper import RmWrapper, RmWrapperManager
from utils.logging import logger


class DbFactory:
    @staticmethod
    def get_wrapper(args) -> (DbWrapperBase, SyncManager):
        if args.db_method == "rm":
            RmWrapperManager.register('RmWrapper', RmWrapper)
            rm_wrapper_manager = RmWrapperManager()
            rm_wrapper_manager.start()
            rm_wrapper = rm_wrapper_manager.RmWrapper(args)
            return rm_wrapper, rm_wrapper_manager
            # return RmWrapper(args)
        elif args.db_method == "monocle":
            MonocleWrapperManager.register('MonocleWrapper', MonocleWrapper)
            monocle_wrapper_manager = MonocleWrapperManager()
            monocle_wrapper_manager.start()
            monocle_wrapper = monocle_wrapper_manager.MonocleWrapper(args)
            return monocle_wrapper, monocle_wrapper_manager
            # return MonocleWrapper(args)
        else:
            logger.error("Invalid db_method in config. Exiting")
            sys.exit(1)
