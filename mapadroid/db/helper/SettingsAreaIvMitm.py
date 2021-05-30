from typing import Dict, Optional

from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import SettingsAreaIvMitm


class SettingsAreaIvMitmHelper:
    @staticmethod
    async def get(session: AsyncSession, instance_id: int, area_id: int) -> Optional[SettingsAreaIvMitm]:
        stmt = select(SettingsAreaIvMitm).where(and_(SettingsAreaIvMitm.instance_id == instance_id,
                                                 SettingsAreaIvMitm.area_id == area_id))
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_all(session: AsyncSession, instance_id: int) -> Dict[int, SettingsAreaIvMitm]:
        stmt = select(SettingsAreaIvMitm).where(SettingsAreaIvMitm.instance_id == instance_id)
        result = await session.execute(stmt)
        retval: Dict[int, SettingsAreaIvMitm] = {}
        for area in result.scalars():
            retval[area.area_id] = area
        return retval
