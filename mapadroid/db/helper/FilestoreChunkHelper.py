from typing import List, AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import FilestoreChunk


class FilestoreChunkHelper:
    @staticmethod
    async def get_chunk_ids(session: AsyncSession, filestore_id: int) -> List[int]:
        stmt = select(FilestoreChunk.chunk_id).where(FilestoreChunk.filestore_id == filestore_id)
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_chunk_data(session: AsyncSession, chunk_id: int):
        stmt = select(FilestoreChunk.data).where(FilestoreChunk.chunk_id == chunk_id)
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_chunk_data_generator(session: AsyncSession, chunk_ids: List[int]) -> AsyncGenerator:
        stmt = select(FilestoreChunk.data).where(FilestoreChunk.chunk_id.in_(chunk_ids))
        result = await session.stream(stmt)

        async for data_chunk in result:
            yield data_chunk.data

    @staticmethod
    async def insert(session: AsyncSession, filestore_id: int, size: int, data: bytes) -> None:
        chunk: FilestoreChunk = FilestoreChunk()
        chunk.filestore_id = filestore_id
        chunk.size = size
        chunk.data = data
        session.add(chunk)
