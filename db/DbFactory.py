import sys
from multiprocessing.managers import SyncManager

from db.DbWrapper import DbWrapper, DbWrapperManager
from utils.logging import logger


class DbFactory:
    @staticmethod
    def get_wrapper(args) -> (DbWrapper, SyncManager):
        if args.db_method == "rm":
            DbWrapperManager.register('DbWrapper', DbWrapper)
            db_wrapper_manager = DbWrapperManager()
            db_wrapper_manager.start()
            db_wrapper = db_wrapper_manager.DbWrapper(args)
            return db_wrapper, db_wrapper_manager
        elif args.db_method == "monocle":
            logger.error(
                "MAD has dropped Monocle support. Please consider checking out the "
                "'migrate_to_rocketmap.sh' script in the scripts folder."
            )
            sys.exit(1)
        else:
            logger.error("Invalid db_method in config. Exiting")
            sys.exit(1)
