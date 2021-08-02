from typing import Dict, Optional

from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import SettingsGeofence


class SettingsGeofenceHelper:
    @staticmethod
    async def get(session: AsyncSession, instance_id: int, geofence_id: int) -> Optional[SettingsGeofence]:
        stmt = select(SettingsGeofence).where(and_(SettingsGeofence.instance_id == instance_id,
                                                   SettingsGeofence.geofence_id == geofence_id))
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_all_mapped(session: AsyncSession, instance_id: int) -> Dict[int, SettingsGeofence]:
        mapped: Dict[int, SettingsGeofence] = {}
        stmt = select(SettingsGeofence).where(SettingsGeofence.instance_id == instance_id)
        result = await session.execute(stmt)
        for fence in result.scalars().all():
            mapped[fence.geofence_id] = fence
        return mapped

    @staticmethod
    async def get_by_name(session: AsyncSession, instance_id: int, name: str) -> Optional[SettingsGeofence]:
        stmt = select(SettingsGeofence).where(and_(SettingsGeofence.instance_id == instance_id,
                                                   SettingsGeofence.name == name))
        result = await session.execute(stmt)
        return result.scalars().first()
