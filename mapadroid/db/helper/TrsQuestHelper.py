from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import TrsQuest


class TrsQuestHelper:
    @staticmethod
    async def get(session: AsyncSession, guid: str) -> Optional[TrsQuest]:
        stmt = select(TrsQuest).where(TrsQuest.GUID == guid)
        result = await session.execute(stmt)
        return result.scalars().first()
