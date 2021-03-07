from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import SettingsDevicepool


class SettingsDevicepoolHelper:
    @staticmethod
    async def get(session: AsyncSession, pool_id: int) -> Optional[SettingsDevicepool]:
        stmt = select(SettingsDevicepool).where(SettingsDevicepool.pool_id == pool_id)
        result = await session.execute(stmt)
        return result.scalars().first()
