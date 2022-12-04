import sys
from typing import Optional

import sqlalchemy

from mapadroid.db.DbWrapper import DbWrapper
from mapadroid.db.PooledQueryExecutor import PooledQueryExecutor
from mapadroid.utils.logging import LoggerEnums, get_logger

logger = get_logger(LoggerEnums.database)


class DbFactory:
    @staticmethod
    async def get_wrapper(args, db_poolsize: Optional[int] = None) -> (DbWrapper, PooledQueryExecutor):
        db_exec = PooledQueryExecutor(args, host=args.dbip, port=args.dbport,
                                      username=args.dbusername, password=args.dbpassword,
                                      database=args.dbname,
                                      poolsize=args.db_poolsize if not db_poolsize else db_poolsize)
        db_wrapper = DbWrapper(db_exec=db_exec, args=args)
        try:
            await db_exec.setup()
            await db_wrapper.setup()
        except sqlalchemy.exc.OperationalError as e:
            logger.critical("Could not setup DB connections: {}", e)
            sys.exit(1)
        return db_wrapper, db_exec
