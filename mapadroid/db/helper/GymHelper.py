from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import Gym


class GymHelper:
    @staticmethod
    async def get(session: AsyncSession, gym_id: str) -> Optional[Gym]:
        stmt = select(Gym).where(Gym.gym_id == gym_id)
        result = await session.execute(stmt)
        return result.scalars().first()
