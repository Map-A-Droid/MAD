from typing import Optional

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.db.model import PokemonDisplay


class PokemonDisplayHelper:
    @staticmethod
    async def insert_ignore(session: AsyncSession, encounter_id: int, pokemon_id: int,
                            gender: Optional[int] = None, form: Optional[int] = None,
                            costume: Optional[int] = None) -> None:
        # SQL Specific IGNORE to execute INSERT IGNORE INTO
        stmt = insert(PokemonDisplay.__tablename__).prefix_with("IGNORE") \
            .values(encounter_id=encounter_id,
                    pokemon=pokemon_id,
                    gender=gender,
                    form=form,
                    costume=costume)
        await session.execute(stmt)
