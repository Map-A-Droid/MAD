from typing import Dict, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import SettingsWalker


class SettingsWalkerHelper:
    @staticmethod
    async def get_all(session: AsyncSession, instance_id: int) -> List[SettingsWalker]:
        stmt = select(SettingsWalker).where(SettingsWalker.instance_id == instance_id)
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_all_mapped(session: AsyncSession, instance_id: int) -> Dict[int, SettingsWalker]:
        all_walkers: List[SettingsWalker] = await SettingsWalkerHelper.get_all(session, instance_id)
        mapped: Dict[int, SettingsWalker] = {}
        for walker in all_walkers:
            mapped[walker.walker_id] = walker
        return mapped
