import datetime
import time

from sqlalchemy import delete, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.db.model import TrsStatsDetectWildMonRaw


class TrsStatsDetectWildMonRawHelper:
    @staticmethod
    async def add(session: AsyncSession, worker: str, encounter_id: int,
                  count: int, is_shiny: bool, timestamp_scan: datetime) -> None:
        stat = TrsStatsDetectWildMonRaw()
        stat.worker = worker
        stat.encounter_id = encounter_id
        stat.count = count
        stat.is_shiny = 1 if is_shiny else 0
        stat.first_seen = timestamp_scan
        stat.last_seen = timestamp_scan
        session.add(stat)

    @staticmethod
    async def cleanup(session: AsyncSession, delete_before_timestap_scan: datetime.datetime, raw_delete_shiny_days: int = 0) -> None:
        where_condition = and_(TrsStatsDetectWildMonRaw.last_seen < delete_before_timestap_scan,
                               TrsStatsDetectWildMonRaw.is_shiny == 0)
        if raw_delete_shiny_days > 0:
            delete_shinies_before_timestamp = int(time.time()) - raw_delete_shiny_days * 86400
            delete_shinies_before = datetime.datetime.utcfromtimestamp(delete_shinies_before_timestamp)
            shiny_condition = and_(TrsStatsDetectWildMonRaw.last_seen < delete_shinies_before,
                                   TrsStatsDetectWildMonRaw.is_shiny == 1)
            where_condition = or_(where_condition, shiny_condition)
        stmt = delete(TrsStatsDetectWildMonRaw) \
            .where(where_condition)
        await session.execute(stmt)
