from typing import Optional

from sqlalchemy import and_, delete, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import Pokestop, TrsVisited
from mapadroid.utils.collections import Location


class TrsVisitedHelper:
    @staticmethod
    async def get(session: AsyncSession, username: str, stop_id: str) -> Optional[TrsVisited]:
        stmt = select(TrsVisited).where(and_(TrsVisited.username == username,
                                             TrsVisited.pokestop_id == stop_id))
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def flush_all_of_username(session: AsyncSession, username: str) -> None:
        stmt = delete(TrsVisited).where(TrsVisited.username == username)
        await session.execute(stmt)

    @staticmethod
    async def mark_visited(session: AsyncSession, username: str, stop_id: str) -> None:
        visited: Optional[TrsVisited] = await TrsVisitedHelper.get(session, username, stop_id)
        if not visited:
            visited = TrsVisited()
            visited.username = username
            visited.pokestop_id = stop_id
            session.add(visited)
