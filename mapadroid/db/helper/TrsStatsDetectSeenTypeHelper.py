from datetime import datetime
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import TrsStatsDetectSeenType
from mapadroid.utils.logging import LoggerEnums, get_logger

logger = get_logger(LoggerEnums.database)


# noinspection PyComparisonWithNone
class TrsStatsDetectSeenTypeHelper:
    @staticmethod
    async def get(session: AsyncSession, encounter_id: int) -> Optional[TrsStatsDetectSeenType]:
        stmt = select(TrsStatsDetectSeenType).where(TrsStatsDetectSeenType.encounter_id == encounter_id)
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def create_or_update(session, stat_entry: TrsStatsDetectSeenType) -> None:
        existing: Optional[TrsStatsDetectSeenType] = await TrsStatsDetectSeenTypeHelper.get(session,
                                                                                            stat_entry.encounter_id)
        if not existing:
            session.add(stat_entry)
        else:
            # Update existing with instance
            if not existing.wild or stat_entry.wild and existing.wild > stat_entry.wild:
                existing.wild = stat_entry.wild
            if not existing.encounter or stat_entry.encounter and existing.encounter > stat_entry.encounter:
                existing.encounter = stat_entry.encounter
            if not existing.lure_encounter or stat_entry.lure_encounter \
                    and existing.lure_encounter > stat_entry.lure_encounter:
                existing.lure_encounter = stat_entry.lure_encounter
            if not existing.lure_wild or stat_entry.lure_wild and existing.lure_wild > stat_entry.lure_wild:
                existing.lure_wild = stat_entry.lure_wild
            if not existing.nearby_cell or stat_entry.nearby_cell and existing.nearby_cell > stat_entry.nearby_cell:
                existing.nearby_cell = stat_entry.nearby_cell
            if not existing.nearby_stop or stat_entry.nearby_stop and existing.nearby_stop > stat_entry.nearby_stop:
                existing.nearby_stop = stat_entry.nearby_stop
            session.add(existing)
