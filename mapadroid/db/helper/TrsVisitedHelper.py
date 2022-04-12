from typing import Optional

from sqlalchemy import delete, insert, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import TrsVisited, Pokestop
from mapadroid.utils.collections import Location


class TrsVisitedHelper:
    @staticmethod
    async def get(session: AsyncSession, origin: str, stop_id: str) -> Optional[TrsVisited]:
        stmt = select(TrsVisited).where(and_(TrsVisited.origin == origin,
                                             TrsVisited.pokestop_id == stop_id))
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def flush_all_of_origin(session: AsyncSession, origin: str) -> None:
        stmt = delete(TrsVisited).where(TrsVisited.origin == origin)
        await session.execute(stmt)

    @staticmethod
    async def mark_visited_by_location(session: AsyncSession, origin: str, location: Location) -> None:
        from mapadroid.db.helper.PokestopHelper import PokestopHelper
        pokestop: Optional[Pokestop] = await PokestopHelper.get_at_location(session, location)
        if not pokestop:
            return
        stmt = insert(TrsVisited).values(pokestop_id=pokestop.pokestop_id, origin=origin).prefix_with("IGNORE")
        await session.execute(stmt)

    @staticmethod
    async def mark_visited(session: AsyncSession, origin: str, stop_id: str) -> None:
        visited: Optional[TrsVisited] = await TrsVisitedHelper.get(session, origin, stop_id)
        if not visited:
            visited = TrsVisited()
            visited.origin = origin
            visited.pokestop_id = stop_id
            session.add(visited)
