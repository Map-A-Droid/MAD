from datetime import datetime, timedelta
from typing import Optional, List

from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import TrsUsage
from mapadroid.utils.logging import LoggerEnums, get_logger

logger = get_logger(LoggerEnums.database)


# noinspection PyComparisonWithNone
class TrsUsageHelper:
    @staticmethod
    async def add(session: AsyncSession, instance: str, cpu: float, mem: float, garbage: int,
                  timestamp: int) -> None:
        """
        DbWrapper::insert_usage
        Args:
            session:
            instance:
            cpu:
            mem:
            garbage:
            timestamp:

        Returns:

        """
        usage: TrsUsage = TrsUsage()
        usage.instance = instance
        usage.cpu = cpu
        usage.memory = mem
        usage.garbage = garbage
        usage.timestamp = timestamp
        session.add(usage)

    @staticmethod
    async def get_usages(session: AsyncSession, last_n_minutes: Optional[int] = 120,
                         instance_name: Optional[str] = None) -> List[TrsUsage]:
        """
        Instead of DbStatsReader::get_usage_count
        Args:
            session:
            last_n_minutes:
            instance_name:

        Returns: Simply return all usage entries for the constraints given (if any) sorted by their time of creation

        """
        stmt = select(TrsUsage)
        where_conditions = []
        if last_n_minutes:
            time_to_check_after = datetime.utcnow() - timedelta(minutes=last_n_minutes)
            where_conditions.append(TrsUsage.timestamp > time_to_check_after.timestamp())
        if instance_name:
            where_conditions.append(TrsUsage.instance == instance_name)
        stmt = stmt.where(and_(*where_conditions))\
            .order_by(TrsUsage.timestamp)
        result = await session.execute(stmt)
        return result.scalars().all()
