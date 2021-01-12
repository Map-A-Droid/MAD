import sys
from multiprocessing.managers import SyncManager

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.PooledQueryExecutor import (PooledQueryExecutor,
                                              PooledQuerySyncManager)
from mapadroid.utils.logging import LoggerEnums, get_logger

logger = get_logger(LoggerEnums.database)


class DbFactory:
    @staticmethod
    def get_wrapper(args) -> (DbWrapper, SyncManager):
        if args.db_method == "monocle":
            logger.error(
                "MAD has dropped Monocle support. Please consider checking out the "
                "'migrate_to_rocketmap.sh' script in the scripts folder."
            )
            sys.exit(1)
        elif args.db_method != "rm":
            logger.error("Invalid db_method in config. Exiting")
            sys.exit(1)

        PooledQuerySyncManager.register("PooledQueryExecutor", PooledQueryExecutor)
        db_pool_manager = PooledQuerySyncManager()
        db_pool_manager.start()
        db_exec = db_pool_manager.PooledQueryExecutor(host=args.dbip, port=args.dbport,
                                                      username=args.dbusername, password=args.dbpassword,
                                                      database=args.dbname, poolsize=args.db_poolsize)
        db_wrapper = DbWrapper(db_exec=db_exec, args=args)

        return db_wrapper, db_pool_manager
