from datetime import datetime
from typing import Optional

from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import TrsEvent


class TrsEventHelper:
    @staticmethod
    async def get_current_event(session: AsyncSession, include_default: bool = False) -> Optional[TrsEvent]:
        if include_default:
            # TODO: order by event_start desc?
            stmt = select(TrsEvent).where(and_(TrsEvent.event_start < datetime.utcnow(),
                                               TrsEvent.event_end > datetime.utcnow()))
        else:
            stmt = select(TrsEvent).where(and_(TrsEvent.event_start < datetime.utcnow(),
                                               TrsEvent.event_end > datetime.utcnow(),
                                               TrsEvent.event_name != "DEFAULT"))
        result = await session.execute(stmt)
        return result.scalars().first()
