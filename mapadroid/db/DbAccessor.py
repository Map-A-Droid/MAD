import asyncio
from typing import Optional

from loguru import logger
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (AsyncEngine, AsyncSession,
                                    create_async_engine)

from mapadroid.db.model import Base


class DbAccessor:
    def __init__(self, connection_data: str, pool_size: int = 10):
        self.__db_engine: Optional[AsyncEngine] = None
        self.__connection_data: str = connection_data
        logger.info("Starting with pool size {}", pool_size)
        self.__pool_size: int = pool_size
        self.__setup_lock = None
        self.__db_access_semaphore: Optional[asyncio.Semaphore] = None

    async def __aenter__(self) -> AsyncSession:
        await self.__db_access_semaphore.acquire()
        return AsyncSession(self.__db_engine, autoflush=True)

    async def __aexit__(self, type_, value, traceback):
        self.__db_access_semaphore.release()

    async def setup(self):
        if not self.__setup_lock:
            self.__setup_lock = asyncio.Lock()
            self.__db_access_semaphore: asyncio.Semaphore = asyncio.Semaphore(value=self.__pool_size)

        async with self.__setup_lock:
            if self.__db_engine is not None:
                return
            self.__db_engine: AsyncEngine = create_async_engine(
                self.__connection_data, echo=False, pool_size=self.__pool_size
            )

    async def tear_down(self):
        async with self.__setup_lock:
            if self.__db_engine is None:
                return
            await self.__db_engine.dispose()

    def get_engine(self) -> AsyncEngine:
        return self.__db_engine

    async def execute(self, sql, args=(), commit=False, **kwargs):
        if not self.__db_access_semaphore:
            await self.setup()
        has_binary = False
        disp_args = []
        if args and type(args) is tuple:
            for value in args:
                if isinstance(value, bytes):
                    disp_args.append(value[:10])
                    has_binary = True
                else:
                    disp_args.append(value)
        else:
            disp_args = (args)
        get_id = kwargs.get('get_id', False)
        get_dict = kwargs.get('get_dict', False)
        raise_exc = kwargs.get('raise_exc', False)
        suppress_log = kwargs.get('suppress_log', False)
        async with self.__db_access_semaphore:
            try:
                async with AsyncSession(self.__db_engine, autocommit=False, autoflush=True) as session:
                    res = await session.execute(sql, args)
                    if not has_binary:
                        logger.debug3(session.statement)
                    else:
                        logger.debug3("SQL: {}", sql)
                        logger.debug3("Args: {}", disp_args)
                    if commit:
                        session.commit()
                        if get_id:
                            return res.lastrowid
                        else:
                            return res.rowcount
                    else:
                        result = res.fetchall()
                        if get_dict:
                            return self.__convert_to_dict(res.column_descriptions, res)
                        return result
            except SQLAlchemyError as err:
                if not suppress_log:
                    logger.error("Failed executing query: {} ({}), error: {}", sql, disp_args, err)
                if raise_exc:
                    raise err
                return None
            except Exception as e:
                logger.error("Unspecified exception in dbWrapper: {}", str(e))
                return None

    def __convert_to_dict(self, descr, rows):
        desc = [n for n in descr]
        return [dict(zip(desc, row)) for row in rows]
