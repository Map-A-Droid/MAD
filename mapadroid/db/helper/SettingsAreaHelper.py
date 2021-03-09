from typing import Dict, List, Optional

from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import (SettingsArea, SettingsAreaIdle,
                                SettingsAreaIvMitm, SettingsAreaMonMitm,
                                SettingsAreaPokestop, SettingsAreaRaidsMitm)


class SettingsAreaHelper:
    @staticmethod
    async def get(session: AsyncSession, instance_id: int, area_id: int) -> Optional[SettingsArea]:
        stmt = select(SettingsArea).where(and_(SettingsArea.instance_id == instance_id,
                                                 SettingsArea.area_id == area_id))
        # TODO: Also fetch from all other tables...
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_all(session: AsyncSession, instance_id: int) -> Dict[int, SettingsArea]:
        # stmt = select(SettingsArea).where(SettingsArea.instance_id == instance_id)
        stmt = select(SettingsAreaIdle).where(SettingsAreaIdle.instance_id == instance_id)
        stmt = select(SettingsAreaIvMitm).where(SettingsAreaIvMitm.instance_id == instance_id)
        stmt = select(SettingsAreaMonMitm).where(SettingsAreaMonMitm.instance_id == instance_id)
        stmt = select(SettingsAreaPokestop).where(SettingsAreaPokestop.instance_id == instance_id)
        stmt = select(SettingsAreaRaidsMitm).where(SettingsAreaRaidsMitm.instance_id == instance_id)
        result = await session.execute(stmt)
        return result.scalars().all()
