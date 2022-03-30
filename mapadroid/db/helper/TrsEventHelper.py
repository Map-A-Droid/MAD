from datetime import datetime
from typing import Optional, List

from loguru import logger
from sqlalchemy import and_, asc, delete, between, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import TrsEvent, TrsSpawn
from mapadroid.utils.DatetimeWrapper import DatetimeWrapper


class TrsEventHelper:
    @staticmethod
    async def get_current_event(session: AsyncSession, include_default: bool = False) -> Optional[TrsEvent]:
        if include_default:
            stmt = select(TrsEvent).where(and_(TrsEvent.event_start < DatetimeWrapper.now(),
                                               TrsEvent.event_end > DatetimeWrapper.now()))
        else:
            stmt = select(TrsEvent).where(and_(TrsEvent.event_start < DatetimeWrapper.now(),
                                               TrsEvent.event_end > DatetimeWrapper.now(),
                                               TrsEvent.event_name != "DEFAULT"))
        stmt = stmt.order_by(desc(TrsEvent.event_start))
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_all(session: AsyncSession, event_id: Optional[int] = None) -> List[TrsEvent]:
        """
        DbWrapper::get_events
        Args:
            session:
            event_id: If defined, only fetches events of the given event ID (i.e. only one...)

        Returns:

        """
        stmt = select(TrsEvent)
        if event_id is not None:
            stmt = stmt.where(TrsEvent.id == event_id)
        stmt.order_by(asc(TrsEvent.id))
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get(session: AsyncSession, event_id: Optional[int] = None) -> Optional[TrsEvent]:
        stmt = select(TrsEvent).where(TrsEvent.id == event_id)
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def delete_including_spawns(session: AsyncSession, event_id: int) -> bool:
        """
        DbWrapper::delete_event
        Args:
            session:
            event_id:

        Returns: False if deletion failed for whatever reason...

        """
        event: Optional[TrsEvent] = await TrsEventHelper.get(session, event_id)
        if not event:
            return False
        await session.delete(event)
        # Now delete all spawns
        stmt = delete(TrsSpawn).where(TrsSpawn.eventid == event_id)
        await session.execute(stmt)
        return True

    @staticmethod
    async def save(session: AsyncSession, event_name: str, event_start: datetime, event_end: datetime,
                   event_lure_duration: int = 30, event_id: Optional[int] = None) -> None:
        event: TrsEvent = TrsEvent()
        if event_id:
            event.id = event_id
        event.event_name = event_name
        event.event_start = event_start
        event.event_end = event_end
        event.event_lure_duration = event_lure_duration
        await session.merge(event)
        await session.flush([event])

    @staticmethod
    async def is_event_active(session: AsyncSession, event_id: int) -> bool:
        """
        Used to be DbWrapper::check_if_event_is_active
        Args:
            session:
            event_id:

        Returns:

        """
        logger.debug3("DbWrapper::check_if_event_is_active called")
        if event_id == 1:
            return False
        stmt = select(TrsEvent).where(and_(TrsEvent.id == event_id,
                                           between(DatetimeWrapper.now(), TrsEvent.event_start, TrsEvent.event_end)))

        result = await session.execute(stmt)
        return result.scalars().first() is not None
