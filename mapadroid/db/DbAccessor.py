import asyncio
from typing import Optional

from loguru import logger
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (AsyncEngine, AsyncSession,
                                    create_async_engine)


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

    @staticmethod
    def __convert_to_dict(descr, rows):
        desc = [n for n in descr]
        return [dict(zip(desc, row)) for row in rows]
