from datetime import datetime
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import Weather


class WeatherHelper:
    @staticmethod
    async def get(session: AsyncSession, s2_cell_id: str) -> Optional[Weather]:
        stmt = select(Weather).where(Weather.s2_cell_id == s2_cell_id)
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_changed_since(session: AsyncSession, _timestamp: int) -> List[Weather]:
        stmt = select(Weather).where(Weather.last_updated > datetime.fromtimestamp(_timestamp))
        result = await session.execute(stmt)
        return result.scalars().all()
