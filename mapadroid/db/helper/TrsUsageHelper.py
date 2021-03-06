from sqlalchemy.ext.asyncio import AsyncSession

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