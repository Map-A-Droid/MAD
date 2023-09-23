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
    async def delete_older_than_n_hours(session: AsyncSession, hours: int, limit: Optional[int]) -> None:
        where_condition = PokestopIncident.incident_expiration < DatetimeWrapper.now() - datetime.timedelta(hours=hours)
        stmt = delete(PokestopIncident).where(where_condition)
        if limit:
            # Rather ugly construct as stmt.with_dialect_options currently does not work
            # See https://groups.google.com/g/sqlalchemy/c/WDKhyAt6eAk/m/feteFNZnAAAJ
            stmt = text(f"{str(stmt)} LIMIT :limit")
            result = await session.execute(stmt,
                                  {
                                      "incident_expiration_1": DatetimeWrapper.now() - datetime.timedelta(hours=hours),
                                      "limit": limit
                                  }
                                  )
            # The resulting object is of type CursorResult -> rowcount is available
            logger.info("Removed {} rows of incidents", result.rowcount)
        else:
            await session.execute(stmt)

    @staticmethod
    async def run_optimize(session: AsyncSession) -> None:
        stmt = text(f"OPTIMIZE TABLE {PokestopIncident.__tablename__}")
        await session.execute(stmt)
