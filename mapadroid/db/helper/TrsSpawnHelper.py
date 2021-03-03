from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import TrsSpawn


class TrsSpawnHelper:
    @staticmethod
    async def get(session: AsyncSession, spawn_id: int) -> Optional[TrsSpawn]:
        stmt = select(TrsSpawn).where(TrsSpawn.spawnpoint == spawn_id)
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_all(session: AsyncSession, spawn_ids: List[int]) -> List[TrsSpawn]:
        # TODO: Probably gotta adjust...
        stmt = select(TrsSpawn).where(TrsSpawn.spawnpoint.in_(spawn_ids))
        result = await session.execute(stmt)
        return result.scalars().all()
