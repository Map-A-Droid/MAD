from typing import Dict, Optional

from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import SettingsAreaPokestop


class SettingsAreaPokestopHelper:
    @staticmethod
    async def get(session: AsyncSession, instance_id: int, area_id: int) -> Optional[SettingsAreaPokestop]:
        stmt = select(SettingsAreaPokestop).where(and_(SettingsAreaPokestop.instance_id == instance_id,
                                                       SettingsAreaPokestop.area_id == area_id))
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_all(session: AsyncSession, instance_id: int) -> Dict[int, SettingsAreaPokestop]:
        stmt = select(SettingsAreaPokestop).where(SettingsAreaPokestop.instance_id == instance_id)
        result = await session.execute(stmt)
        retval: Dict[int, SettingsAreaPokestop] = {}
        for area in result.scalars().all():
            retval[area.area_id] = area
        return retval
