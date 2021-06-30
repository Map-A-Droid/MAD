import time
from typing import List, Optional, Tuple

from sqlalchemy import and_, func
from sqlalchemy import desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import AutoconfigLog


class AutoconfigLogsHelper:
    @staticmethod
    async def get_all_of_instance(session: AsyncSession, instance_id: int,
                                  session_id: Optional[int] = None) -> List[AutoconfigLog]:
        stmt = select(AutoconfigLog).where(AutoconfigLog.instance_id == instance_id)
        if session_id:
            stmt = stmt.where(AutoconfigLog.session_id == session_id)
        stmt = stmt.order_by(desc(AutoconfigLog.log_time))
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_transformed(session: AsyncSession, instance_id: int,
                              session_id: Optional[int] = None) -> List[Tuple[int, int, str]]:
        """

        Args:
            session:
            instance_id:
            session_id:

        Returns: List of tuples consisting of unix_timestamp (log_time), level and message

        """
        all_of_instance: List[AutoconfigLog] = await AutoconfigLogHelper.get_all_of_instance(session, instance_id,
                                                                                             session_id)
        transformed_list: List[Tuple[int, int, str]] = []
        for log in all_of_instance:
            timestamp: int = int(time.mktime(log.log_time.timetuple()))
            transformed_list.append((timestamp, log.level, log.msg))
        return transformed_list

    @staticmethod
    async def get_max_level_of_session(session: AsyncSession, instance_id: int,
                                       session_id: int) -> Optional[int]:
        stmt = select(func.MAX(AutoconfigLog.level)).where(and_(AutoconfigLog.instance_id == instance_id,
                                                                AutoconfigLog.session_id == session_id))
        result = await session.execute(stmt)
        return result.scalars().first()
