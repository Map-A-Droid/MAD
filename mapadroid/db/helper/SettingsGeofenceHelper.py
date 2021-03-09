from typing import Optional

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
