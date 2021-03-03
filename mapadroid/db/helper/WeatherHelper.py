from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import Weather


class WeatherHelper:
    @staticmethod
    async def get(session: AsyncSession, s2_cell_id: str) -> Optional[Weather]:
        stmt = select(Weather).where(Weather.s2_cell_id == s2_cell_id)
        result = await session.execute(stmt)
        return result.scalars().first()
