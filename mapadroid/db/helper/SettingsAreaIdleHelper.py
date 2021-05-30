from typing import Dict, List, Optional

from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import SettingsAreaIdle


class SettingsAreaIdleHelper:
    @staticmethod
    async def get(session: AsyncSession, instance_id: int, area_id: int) -> Optional[SettingsAreaIdle]:
        stmt = select(SettingsAreaIdle).where(and_(SettingsAreaIdle.instance_id == instance_id,
                                                 SettingsAreaIdle.area_id == area_id))
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_all(session: AsyncSession, instance_id: int) -> Dict[int, SettingsAreaIdle]:
        stmt = select(SettingsAreaIdle).where(SettingsAreaIdle.instance_id == instance_id)
        result = await session.execute(stmt)
        retval: Dict[int, SettingsAreaIdle] = {}
        for area in result.scalars():
            retval[area.area_id] = area
        return retval
