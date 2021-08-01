
from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.PooledQueryExecutor import PooledQueryExecutor
from mapadroid.utils.logging import LoggerEnums, get_logger

logger = get_logger(LoggerEnums.database)


class DbFactory:
    @staticmethod
    def get_wrapper(args) -> (DbWrapper, PooledQueryExecutor):
        db_exec = PooledQueryExecutor(args, host=args.dbip, port=args.dbport,
                                      username=args.dbusername, password=args.dbpassword,
                                      database=args.dbname, poolsize=args.db_poolsize)
        db_wrapper = DbWrapper(db_exec=db_exec, args=args)
        return db_wrapper, db_exec
