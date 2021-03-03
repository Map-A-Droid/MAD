from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import TrsS2Cell


class TrsS2CellHelper:
    @staticmethod
    async def get(session: AsyncSession, cell_id: int) -> Optional[TrsS2Cell]:
        stmt = select(TrsS2Cell).where(TrsS2Cell.id == cell_id)
        result = await session.execute(stmt)
        return result.scalars().first()
