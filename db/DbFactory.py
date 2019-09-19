import sys
from multiprocessing.managers import SyncManager

from db.dbWrapperBase import DbWrapperBase
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
        elif args.db_method == "monocle":
            logger.error(
                "MAD has dropped Monocle support. Please consider checking out the "
                "'migrate_to_rocketmap.sh' script in the scripts folder."
            )
            sys.exit(1)
        else:
            logger.error("Invalid db_method in config. Exiting")
            sys.exit(1)
