from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import SettingsWalker


class SettingsWalkerHelper:
    @staticmethod
    async def get_all(session: AsyncSession, instance_id: int) -> List[SettingsWalker]:
        stmt = select(SettingsWalker).where(SettingsWalker.instance_id == instance_id)
        result = await session.execute(stmt)
        return result.scalars().all()
