from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.db.model import TrsStatsDetectFortRaw


class TrsStatsDetectFortRawHelper:
    @staticmethod
    async def add(session: AsyncSession, worker: str, guid: str, type_of_mon_detection: str,
                  count: int, timestamp_scan: int) -> None:
        stat = TrsStatsDetectFortRaw()
        stat.worker = worker
        stat.guid = guid
        stat.type = type_of_mon_detection
        stat.count = count
        stat.timestamp_scan = timestamp_scan
        session.add(stat)

    @staticmethod
    async def cleanup(session: AsyncSession, delete_before_timestap_scan: int) -> None:
        stmt = delete(TrsStatsDetectFortRaw).where(TrsStatsDetectFortRaw.timestamp_scan < delete_before_timestap_scan)
        await session.execute(stmt)
