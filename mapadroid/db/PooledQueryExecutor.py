from threading import Lock
from typing import Optional, Union

import aioredis as aioredis
from aioredis import Redis

from mapadroid.cache import NoopCache
from mapadroid.db.DbAccessor import DbAccessor
from loguru import logger


class PooledQueryExecutor:
    def __init__(self, args, host, port, username, password, database, poolsize=2):
        self.args = args
        self.host = host
        self.port = port
        self.user = username
        self.password = password
        self.database = database
        self._poolsize = poolsize

        self._pool_mutex = Lock()

        self._db_accessor: Optional[DbAccessor] = None
        self._async_db_initiated = False
        self._redis_cache: Optional[Union[Redis, NoopCache]] = None
        self._init_pool()

    def get_db_accessor(self) -> DbAccessor:
        return self._db_accessor

    async def setup(self):
        # TODO: Shutdown...
        with self._pool_mutex:
            await self._db_accessor.setup()
            if self.args.enable_cache:
                redis_credentials = {"host": self.args.cache_host, "port": self.args.cache_port}
                if self.args.cache_password:
                    redis_credentials["password"] = self.args.cache_password
                if self.args.cache_database:
                    redis_credentials["db"] = self.args.cache_password
                self._redis_cache: Redis = await aioredis.Redis(**redis_credentials)
            else:
                self._redis_cache: NoopCache = NoopCache()

    async def get_cache(self) -> Union[Redis, NoopCache]:
        if self._redis_cache is None:
            await self.setup()
        return self._redis_cache

    def _init_pool(self):
        logger.info("Connecting to DB")
        with self._pool_mutex:
            self._db_accessor: DbAccessor = DbAccessor(
                f"mysql+aiomysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}", self._poolsize)
