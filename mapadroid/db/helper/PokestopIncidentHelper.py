from datetime import datetime
from operator import or_
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import Pokestop, TrsQuest, TrsVisited, PokestopIncident
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.utils.DatetimeWrapper import DatetimeWrapper
from mapadroid.utils.collections import Location
from mapadroid.utils.logging import LoggerEnums, get_logger
from mapadroid.utils.madGlobals import QuestLayer
from mapadroid.utils.timezone_util import get_timezone_at

logger = get_logger(LoggerEnums.database)


class PokestopIncidentHelper:
    @staticmethod
    async def get(session: AsyncSession, pokestop_id: str, incident_id: str) -> Optional[PokestopIncident]:
        stmt = select(PokestopIncident).where(and_(PokestopIncident.pokestop_id == pokestop_id,
                                                   PokestopIncident.incident_id == incident_id))
        result = await session.execute(stmt)
        return result.scalars().first()
