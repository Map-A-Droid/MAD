from typing import Optional

from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import SettingsArea


class SettingsAreaHelper:
    @staticmethod
    async def get(session: AsyncSession, instance_id: int, area_id: int) -> Optional[SettingsArea]:
        stmt = select(SettingsArea).where(and_(SettingsArea.instance_id == instance_id,
                                               SettingsArea.area_id == area_id))
        result = await session.execute(stmt)
        return result.scalars().first()
