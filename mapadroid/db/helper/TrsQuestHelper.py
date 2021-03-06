from datetime import datetime
from typing import Optional

from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import TrsQuest, Pokestop


class TrsQuestHelper:
    @staticmethod
    async def get(session: AsyncSession, guid: str) -> Optional[TrsQuest]:
        stmt = select(TrsQuest).where(TrsQuest.GUID == guid)
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def check_stop_has_quest(session: AsyncSession, latitude: float, longitude: float) -> bool:
        stmt = select(TrsQuest) \
            .select_from(TrsQuest).join(Pokestop, Pokestop.pokestop_id == TrsQuest.GUID) \
            .where(and_(Pokestop.latitude == latitude, Pokestop.longitude == longitude))
        result = await session.execute(stmt)
        quest: Optional[TrsQuest] = result.scalars().first()
        # Likely only one stop/quest anyway... this method should be removed because it just hurts to lookup a quest
        # using lat,lng
        if quest is None:
            return False
        # Simply check if the quest_timestamp was of today...
        return datetime.utcfromtimestamp(quest.quest_timestamp).date() == datetime.today().date()

