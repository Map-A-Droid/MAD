import asyncio
import os
import sys
from datetime import datetime
from threading import Lock
from typing import Optional

import redis as Redis
from aiofile import async_open
from loguru import logger
from redis import asyncio as aioredis
from sqlalchemy import text

from alembic import command
from alembic.config import Config
from mapadroid.db.DbAccessor import DbAccessor
from mapadroid.db.helper.TrsEventHelper import TrsEventHelper
from mapadroid.utils.DatetimeWrapper import DatetimeWrapper


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
        self._redis_cache: Optional[Redis] = None

    def get_db_accessor(self) -> DbAccessor:
        return self._db_accessor

    async def shutdown(self) -> None:
        await self._db_accessor.tear_down()

    async def setup(self):
        # TODO: Shutdown...
        with self._pool_mutex:
            await self._init_pool()
            if self.args.cache_socket:
                redis_credentials = {"unix_socket_path": self.args.cache_socket}
            else:
                redis_credentials = {"host": self.args.cache_host, "port": self.args.cache_port}
            if self.args.cache_username:
                redis_credentials["username"] = self.args.cache_username
            if self.args.cache_password:
                redis_credentials["password"] = self.args.cache_password
            if self.args.cache_database:
                redis_credentials["db"] = self.args.cache_database
            self._redis_cache: Redis = await aioredis.Redis(**redis_credentials)
            await self._redis_cache.ping()

    async def get_cache(self) -> Redis:
        if self._redis_cache is None:
            await self.setup()
        return self._redis_cache

    def run_migrations(self, db_uri: str) -> None:
        logger.info('Running DB migrations')
        alembic_cfg = Config()
        alembic_cfg.set_main_option('script_location', 'alembic')
        alembic_cfg.set_main_option('sqlalchemy.url', db_uri)
        command.upgrade(alembic_cfg, 'head')

    async def _init_pool(self):
        # Run Alembic DB migrations
        if self.args.dbsocket:
            db_uri: str = (f"mysql+aiomysql://{self.user}:{self.password}@/{self.database}"
                           f"?unix_socket={self.args.dbsocket}")
        else:
            db_uri: str = f"mysql+aiomysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


        logger.info("Connecting to DB")
        self._db_accessor: DbAccessor = DbAccessor(db_uri, self._poolsize)
        await self._db_accessor.setup()

        loop = asyncio.get_running_loop()
        await self.initialize_db()
        await loop.run_in_executor(None, self.run_migrations, db_uri)

    async def initialize_db(self):
        try:
            async with self._db_accessor as session, session:
                # TODO: Probably can be written in a nicer way or master's "sanity checker" adapted?
                check_table_exists = f"""
                SELECT COUNT(TABLE_NAME)
                FROM
                   information_schema.TABLES
                WHERE
                   TABLE_SCHEMA LIKE '{self.database}' AND
                    TABLE_TYPE LIKE 'BASE TABLE' AND
                    TABLE_NAME = 'pokemon';
                """
                table_exists_result = await session.execute(text(check_table_exists))
                table_exists = table_exists_result.first()[0]
                if table_exists == 1:
                    return

                sql_file = ["scripts", "SQL", "mad.sql"]
                async with async_open(os.path.join(*sql_file), "r") as fh:
                    tables = "".join(await fh.read()).split(";")
                    for table in tables:
                        install_cmd = '%s;%s;%s'
                        args = ('SET FOREIGN_KEY_CHECKS=0', 'SET NAMES utf8mb4', table)
                        await session.execute(text(install_cmd % args))
                        await session.commit()
            logger.success('Successfully initialized database')
            await self.__add_default_event()
        except Exception:
            logger.opt(exception=True).critical('Unable to install default MAD schema.  Please install the schema from '
                                                'scripts/SQL/mad.sql')
            sys.exit(1)

    async def __add_default_event(self):
        async with self._db_accessor as session:
            await TrsEventHelper.save(session, event_name="DEFAULT", event_start=DatetimeWrapper.fromtimestamp(0),
                                      event_end=datetime.now().replace(year=2099), event_lure_duration=30)
            await session.commit()
