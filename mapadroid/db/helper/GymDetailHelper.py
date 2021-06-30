from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import GymDetail


class GymDetailHelper:
    @staticmethod
    async def get(session: AsyncSession, gym_id: str) -> Optional[GymDetail]:
        stmt = select(GymDetail).where(GymDetail.gym_id == gym_id)
        result = await session.execute(stmt)
        return result.scalars().first()
