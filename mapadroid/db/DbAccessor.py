import asyncio
from typing import Optional

from sqlalchemy.ext.asyncio import (AsyncEngine, AsyncSession,
                                    create_async_engine)

from mapadroid.db.model import Base


class DbAccessor:
    def __init__(self, connection_data: str, pool_size: int = 10):
        self.__db_engine: Optional[AsyncEngine] = None
        self.__connection_data: str = connection_data
        self.__pool_size: int = pool_size
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.__setup_lock = asyncio.Lock()
        self.__db_access_semaphore: asyncio.Semaphore = asyncio.Semaphore(value=pool_size)

    async def setup(self):
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

    async def run_in_session(self, coroutine, **kw):
        async with self.__db_access_semaphore:
            async with AsyncSession(self.__db_engine, autocommit=False, autoflush=True) as session:
                return await coroutine(session, **kw)

    async def immediate_save(self, instance: Base):
        async with self.__db_access_semaphore:
            async with AsyncSession(self.__db_engine, autocommit=False, autoflush=True) as session:
                session.add(instance)
                session.commit()

    async def execute(self, sql, args=(), commit=False, **kwargs):
        async with self.__db_access_semaphore:
            async with AsyncSession(self.__db_engine, autocommit=False, autoflush=True) as session:
                res = await session.execute(sql, args)
                if commit:
                    session.commit()
                return res.fetchall()
