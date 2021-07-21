import datetime
import time
from typing import Optional

from sqlalchemy import delete, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.db.model import TrsStatsDetectWildMonRaw


class TrsStatsDetectWildMonRawHelper:
    @staticmethod
    async def get(session: AsyncSession, worker: str, encounter_id: int) -> Optional[TrsStatsDetectWildMonRaw]:
        stmt = select(TrsStatsDetectWildMonRaw).where(and_(TrsStatsDetectWildMonRaw.worker == worker,
                                                           TrsStatsDetectWildMonRaw.encounter_id == encounter_id))
        result = await session.execute(stmt)
        return result.scalars().first

    @staticmethod
    async def create_or_update(session: AsyncSession, instance: TrsStatsDetectWildMonRaw) -> None:
        existing: Optional[TrsStatsDetectWildMonRaw] = await TrsStatsDetectWildMonRawHelper.get(session,
                                                                                                instance.worker,
                                                                                                instance.encounter_id)
        if not existing:
            session.add(instance)
        else:
            # Update existing with instance
            if existing.first_scanned > instance.first_scanned:
                existing.first_scanned = instance.first_scanned
            if existing.last_scanned < instance.last_scanned:
                existing.last_scanned = instance.last_scanned
            existing.count = instance.count + existing.count
            if instance.is_shiny:
                existing.is_shiny = instance.is_shiny
            session.add(existing)

    @staticmethod
    async def cleanup(session: AsyncSession, delete_before_timestap_scan: datetime.datetime, raw_delete_shiny_days: int = 0) -> None:
        where_condition = and_(TrsStatsDetectWildMonRaw.last_scanned < delete_before_timestap_scan,
                               TrsStatsDetectWildMonRaw.is_shiny == 0)
        if raw_delete_shiny_days > 0:
            delete_shinies_before_timestamp = int(time.time()) - raw_delete_shiny_days * 86400
            delete_shinies_before = datetime.datetime.fromtimestamp(delete_shinies_before_timestamp)
            shiny_condition = and_(TrsStatsDetectWildMonRaw.last_scanned < delete_shinies_before,
                                   TrsStatsDetectWildMonRaw.is_shiny == 1)
            where_condition = or_(where_condition, shiny_condition)
        stmt = delete(TrsStatsDetectWildMonRaw) \
            .where(where_condition)
        await session.execute(stmt)
