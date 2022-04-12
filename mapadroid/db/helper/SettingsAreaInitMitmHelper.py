from typing import Dict, Optional

from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import SettingsAreaInitMitm


class SettingsAreaInitMitmHelper:
    @staticmethod
    async def get(session: AsyncSession, instance_id: int, area_id: int) -> Optional[SettingsAreaInitMitm]:
        stmt = select(SettingsAreaInitMitm).where(and_(SettingsAreaInitMitm.instance_id == instance_id,
                                                       SettingsAreaInitMitm.area_id == area_id))
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_all(session: AsyncSession, instance_id: int) -> Dict[int, SettingsAreaInitMitm]:
        stmt = select(SettingsAreaInitMitm).where(SettingsAreaInitMitm.instance_id == instance_id)
        result = await session.execute(stmt)
        retval: Dict[int, SettingsAreaInitMitm] = {}
        for area in result.scalars().all():
            retval[area.area_id] = area
        return retval
