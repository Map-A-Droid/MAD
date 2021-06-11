from datetime import datetime, timedelta
from typing import Optional, List, Tuple

from sqlalchemy import and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import TrsQuest, Pokestop
from mapadroid.utils.collections import Location


class TrsQuestHelper:
    @staticmethod
    async def get(session: AsyncSession, guid: str) -> Optional[TrsQuest]:
        stmt = select(TrsQuest).where(TrsQuest.GUID == guid)
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def check_stop_has_quest(session: AsyncSession, location: Location) -> bool:
        stmt = select(TrsQuest) \
            .select_from(TrsQuest).join(Pokestop, Pokestop.pokestop_id == TrsQuest.GUID) \
            .where(and_(Pokestop.latitude == location.lat, Pokestop.longitude == location.lng))
        result = await session.execute(stmt)
        quest: Optional[TrsQuest] = result.scalars().first()
        # Likely only one stop/quest anyway... this method should be removed because it just hurts to lookup a quest
        # using lat,lng
        if quest is None:
            return False
        # Simply check if the quest_timestamp was of today...
        return datetime.utcfromtimestamp(quest.quest_timestamp).date() == datetime.today().date()

    @staticmethod
    async def get_quests_counts(session: AsyncSession, last_n_days: Optional[int] = None) -> List[Tuple[int, int]]:
        """
        DbStatsReader::get_quests_count
        Args:
            last_n_days:
            session:

        Returns: List of tuples with (full_hour_timestamp, count of quests)

        """
        date_query = func.UNIX_TIMESTAMP(
            func.DATE_FORMAT(
                func.FROM_UNIXTIME(
                    func.MIN(TrsQuest.quest_timestamp)),
                '%y-%m-%d %k:00:00'
            )
        )

        stmt = select(date_query, func.COUNT(TrsQuest.GUID))\
            .select_from(TrsQuest)
        if last_n_days:
            time_to_check_after = datetime.utcnow() - timedelta(days=last_n_days)
            stmt = stmt.where(TrsQuest.quest_timestamp > time_to_check_after.timestamp())
        stmt = stmt.group_by(func.day(func.FROM_UNIXTIME(TrsQuest.quest_timestamp)),
                             func.hour(func.FROM_UNIXTIME(TrsQuest.quest_timestamp)))\
            .order_by(TrsQuest.quest_timestamp)
        result = await session.execute(stmt)
        results: List[Tuple[int, int]] = []
        for timestamp, count in result.all():
            results.append((timestamp, count))
        return results


