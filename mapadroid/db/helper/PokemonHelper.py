from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import Pokemon


class PokemonHelper:
    @staticmethod
    async def get(session: AsyncSession, encounter_id: int) -> Optional[Pokemon]:
        stmt = select(Pokemon).where(Pokemon.encounter_id == encounter_id)
        result = await session.execute(stmt)
        return result.scalars().first()
