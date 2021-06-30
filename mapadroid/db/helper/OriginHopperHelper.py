from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import OriginHopper


class OriginHopperHelper:
    @staticmethod
    async def get(session: AsyncSession, origin: str) -> Optional[OriginHopper]:
        stmt = select(OriginHopper).where(OriginHopper.origin == origin)
        result = await session.execute(stmt)
        return result.scalars().first()
