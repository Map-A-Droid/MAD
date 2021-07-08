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
