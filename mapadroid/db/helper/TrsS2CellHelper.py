from typing import Optional, List

from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.dialects.mysql import insert

from mapadroid.db.model import TrsS2Cell
from mapadroid.utils.collections import Location
from mapadroid.utils.s2Helper import S2Helper


class TrsS2CellHelper:
    @staticmethod
    async def get(session: AsyncSession, cell_id: int) -> Optional[TrsS2Cell]:
        stmt = select(TrsS2Cell).where(TrsS2Cell.id == cell_id)
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def insert_update_cell(session: AsyncSession, cell: dict) -> None:
        cell_id = cell["id"]
        if cell_id < 0:
            cell_id = cell_id + 2 ** 64
        lat, lng, _ = S2Helper.get_position_from_cell(cell_id)
        insert_stmt = insert(TrsS2Cell).values(
            id=cell_id,
            level=15,
            center_latitude=lat,
            center_longitude=lng,
            updated=int(cell["current_timestamp"] / 1000)
        )
        on_duplicate_key_stmt = insert_stmt.on_duplicate_key_update(
            updated=insert_stmt.inserted.data
        )
        await session.execute(on_duplicate_key_stmt)

    @staticmethod
    async def get_cells_in_rectangle(session: AsyncSession,
                                     ne_corner: Optional[Location], sw_corner: Optional[Location],
                                     old_ne_corner: Optional[Location] = None, old_sw_corner: Optional[Location] = None,
                                     timestamp: Optional[int] = None) -> List[TrsS2Cell]:
        stmt = select(TrsS2Cell)
        where_conditions = [and_(TrsS2Cell.center_latitude >= sw_corner.lat,
                                 TrsS2Cell.center_longitude >= sw_corner.lng,
                                 TrsS2Cell.center_latitude <= ne_corner.lat,
                                 TrsS2Cell.center_longitude <= ne_corner.lng)]
        if (old_ne_corner and old_sw_corner
                and old_ne_corner.lat and old_ne_corner.lng and old_sw_corner.lat and old_sw_corner.lng):
            where_conditions.append(and_(TrsS2Cell.center_latitude >= old_sw_corner.lat,
                                         TrsS2Cell.center_longitude >= old_sw_corner.lng,
                                         TrsS2Cell.center_latitude <= old_ne_corner.lat,
                                         TrsS2Cell.center_longitude <= old_ne_corner.lng))
        if timestamp:
            where_conditions.append(TrsS2Cell.updated >= timestamp)

        stmt = stmt.where(and_(*where_conditions))
        result = await session.execute(stmt)
        return result.scalars().all()
