import datetime
from typing import Optional

from sqlalchemy import and_, delete, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import PokestopIncident
from mapadroid.utils.DatetimeWrapper import DatetimeWrapper
from mapadroid.utils.logging import LoggerEnums, get_logger

logger = get_logger(LoggerEnums.database)


class PokestopIncidentHelper:
    @staticmethod
    async def get(session: AsyncSession, pokestop_id: str, incident_id: str) -> Optional[PokestopIncident]:
        stmt = select(PokestopIncident).where(and_(PokestopIncident.pokestop_id == pokestop_id,
                                                   PokestopIncident.incident_id == incident_id))
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def delete_older_than_n_hours(session: AsyncSession, hours: int) -> None:
        where_condition = PokestopIncident.incident_expiration < DatetimeWrapper.now() - datetime.timedelta(hours=hours)
        stmt = delete(PokestopIncident).where(where_condition)
        await session.execute(stmt)

    @staticmethod
    async def run_optimize(session: AsyncSession) -> None:
        stmt = text(f"OPTIMIZE {PokestopIncident.__tablename__}")
        await session.execute(stmt)
