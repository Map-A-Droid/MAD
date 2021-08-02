from typing import Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import SettingsDevicepool


class SettingsDevicepoolHelper:
    @staticmethod
    async def get(session: AsyncSession, pool_id: int) -> Optional[SettingsDevicepool]:
        stmt = select(SettingsDevicepool).where(SettingsDevicepool.pool_id == pool_id)
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_all_mapped(session: AsyncSession, instance_id: int) -> Dict[int, SettingsDevicepool]:
        """

        Args:
            session:
            instance_id:

        Returns: Dict mapping pool_id to SettingsDevicepool

        """
        stmt = select(SettingsDevicepool).where(SettingsDevicepool.instance_id == instance_id)
        result = await session.execute(stmt)
        mapped: Dict[int, SettingsDevicepool] = {}
        for pool in result.scalars().all():
            mapped[pool.pool_id] = pool
        return mapped
