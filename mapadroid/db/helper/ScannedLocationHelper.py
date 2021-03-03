from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.db.model import Scannedlocation


class ScannedLocationHelper:
    @staticmethod
    async def get(session: AsyncSession, cell_id: int) -> Optional[Scannedlocation]:
        stmt = select(Scannedlocation).where(Scannedlocation.cellid == cell_id)
        result = await session.execute(stmt)
        return result.scalars().first()
