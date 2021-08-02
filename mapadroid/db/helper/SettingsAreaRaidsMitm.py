from typing import Dict, Optional

from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import SettingsAreaRaidsMitm


class SettingsAreaRaidsMitmHelper:
    @staticmethod
    async def get(session: AsyncSession, instance_id: int, area_id: int) -> Optional[SettingsAreaRaidsMitm]:
        stmt = select(SettingsAreaRaidsMitm).where(and_(SettingsAreaRaidsMitm.instance_id == instance_id,
                                                        SettingsAreaRaidsMitm.area_id == area_id))
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_all(session: AsyncSession, instance_id: int) -> Dict[int, SettingsAreaRaidsMitm]:
        stmt = select(SettingsAreaRaidsMitm).where(SettingsAreaRaidsMitm.instance_id == instance_id)
        result = await session.execute(stmt)
        retval: Dict[int, SettingsAreaRaidsMitm] = {}
        for area in result.scalars().all():
            retval[area.area_id] = area
        return retval
