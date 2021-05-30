from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import MadminInstance


class MadminInstanceHelper:
    @staticmethod
    async def get_by_name(session: AsyncSession, instance_name: str) -> Optional[MadminInstance]:
        """

        Args:
            session:
            instance_name:

        Returns:

        """
        stmt = select(MadminInstance).where(MadminInstance.name == instance_name)
        result = await session.execute(stmt)
        return result.scalars().first()
