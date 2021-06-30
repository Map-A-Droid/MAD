from typing import Optional

from sqlalchemy import delete, insert
from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.db.model import TrsVisited, Pokestop
from mapadroid.utils.collections import Location


class TrsVisitedHelper:
    @staticmethod
    async def flush_all_of_origin(session: AsyncSession, origin: str) -> None:
        stmt = delete(TrsVisited).where(TrsVisited.origin == origin)
        await session.execute(stmt)

    @staticmethod
    async def mark_visited(session: AsyncSession, origin: str, location: Location) -> None:
        from mapadroid.db.helper.PokestopHelper import PokestopHelper
        pokestop: Optional[Pokestop] = await PokestopHelper.get_at_location(session, location)
        if not pokestop:
            return
        stmt = insert(TrsVisited).values(pokestop_id=pokestop.pokestop_id, origin=origin).prefix_with("IGNORE")
        await session.execute(stmt)
