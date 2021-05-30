from typing import Dict, List, Optional

from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import SettingsAreaMonMitm


class SettingsAreaMonMitmHelper:
    @staticmethod
    async def get(session: AsyncSession, instance_id: int, area_id: int) -> Optional[SettingsAreaMonMitm]:
        stmt = select(SettingsAreaMonMitm).where(and_(SettingsAreaMonMitm.instance_id == instance_id,
                                                 SettingsAreaMonMitm.area_id == area_id))
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_all(session: AsyncSession, instance_id: int) -> Dict[int, SettingsAreaMonMitm]:
        stmt = select(SettingsAreaMonMitm).where(SettingsAreaMonMitm.instance_id == instance_id)
        result = await session.execute(stmt)
        retval: Dict[int, SettingsAreaMonMitm] = {}
        for area in result.scalars():
            retval[area.area_id] = area
        return retval
