import time

from sqlalchemy import delete, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.db.model import TrsStatsDetectMonRaw


class TrsStatsDetectMonRawHelper:
    @staticmethod
    async def add(session: AsyncSession, worker: str, encounter_id: int, type_of_mon_detection: str,
                  count: int, is_shiny: bool, timestamp_scan: int) -> None:
        stat = TrsStatsDetectMonRaw()
        stat.worker = worker
        stat.encounter_id = encounter_id
        stat.type = type_of_mon_detection
        stat.count = count
        stat.is_shiny = 1 if is_shiny else 0
        stat.timestamp_scan = timestamp_scan
        session.add(stat)

    @staticmethod
    async def cleanup(session: AsyncSession, delete_before_timestap_scan: int, raw_delete_shiny_days: int = 0) -> None:
        where_condition = and_(TrsStatsDetectMonRaw.timestamp_scan < delete_before_timestap_scan,
                               TrsStatsDetectMonRaw.is_shiny == 0)
        if raw_delete_shiny_days > 0:
            delete_shinies_before_timestamp = int(time.time()) - raw_delete_shiny_days * 86400
            shiny_condition = and_(TrsStatsDetectMonRaw.timestamp_scan < delete_shinies_before_timestamp,
                                   TrsStatsDetectMonRaw.is_shiny == 1)
            where_condition = or_(where_condition, shiny_condition)
        stmt = delete(TrsStatsDetectMonRaw) \
            .where(where_condition)
        await session.execute(stmt)
