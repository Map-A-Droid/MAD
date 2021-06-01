from multiprocessing import Lock, Semaphore
from typing import Optional, Union

import aioredis as aioredis
from aioredis import Redis

from mapadroid.cache import NoopCache
from mapadroid.db.DbAccessor import DbAccessor
from mapadroid.utils.logging import LoggerEnums, get_logger

logger = get_logger(LoggerEnums.database)


class PooledQueryExecutor:
    def __init__(self, args, host, port, username, password, database, poolsize=2):
        # TODO: Create redis cache elsewhere...
        self.args = args
        self.host = host
        self.port = port
        self.user = username
        self.password = password
        self.database = database
        self._poolsize = poolsize

        self._pool_mutex = Lock()

        self._connection_semaphore = Semaphore(poolsize)
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
                self._redis_cache: Redis = await aioredis.create_redis_pool(address=(self.args.cache_host,
                                                                                     self.args.cache_port),
                                                                            password=self.args.cache_password,
                                                                            db=self.args.cache_database)
            else:
                self._redis_cache: NoopCache = NoopCache()

    async def get_cache(self) -> Union[Redis, NoopCache]:
        if self._redis_cache is None:
            await self.setup()
        return self._redis_cache

    def _init_pool(self):
        logger.info("Connecting to DB")
        with self._pool_mutex:
            self._db_accessor: DbAccessor = DbAccessor(f"mysql+aiomysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}", self._poolsize)

    async def execute_async(self, sql, args=(), commit=False, **kwargs):
        # TODO This sucks...
        with self._pool_mutex:
            if not self._async_db_initiated:
                await self._db_accessor.setup()
                self._async_db_initiated = True
        return await self._db_accessor.execute(sql, args, commit, **kwargs)

    # ===================================================
    # =============== DB Helper Functions ===============
    # ===================================================

    async def autofetch_value_async(self, sql, args=(), **kwargs):
        """ Fetch the first value from the first row """
        data = await self.execute_async(sql, args=args, raise_exc=True, **kwargs)
        if not data or len(data) == 0:
            return None
        return data[0][0]

    async def autofetch_row_async(self, sql, args=(), **kwargs):
        """ Fetch the first row and have it return as a dictionary """
        # TODO - Force LIMIT 1
        data = await self.execute_async(sql, args=args, get_dict=True, raise_exc=True, **kwargs)
        if not data or len(data) == 0:
            return {}
        return data[0]
