from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import Pokestop


class PokestopHelper:
    @staticmethod
    async def get(session: AsyncSession, pokestop_id: str) -> Optional[Pokestop]:
        stmt = select(Pokestop).where(Pokestop.pokestop_id == pokestop_id)
        result = await session.execute(stmt)
        return result.scalars().first()
