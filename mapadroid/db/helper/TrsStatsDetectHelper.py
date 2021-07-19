from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

from sqlalchemy import and_, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import TrsStatsDetect


class TrsStatsDetectHelper:
    @staticmethod
    async def get_detection_count_per_worker(session: AsyncSession, include_last_n_minutes: Optional[int] = None,
                                             hourly: bool = True,
                                             worker: Optional[str] = None) -> Dict[
        str, Dict[int, Tuple[int, int, int, int]]]:
        """
        Fetches the stats of workers (or only one if specified) with hourly-timestamps in the inner dict as keys
        Args:
            session:
            include_last_n_minutes:
            hourly:
            worker:

        Returns:

        """
        stmt = select(func.unix_timestamp(
            func.DATE_FORMAT(func.from_unixtime(func.min(TrsStatsDetect.timestamp_scan)), '%y-%m-%d %k:00:00')),
                      TrsStatsDetect.worker,
                      func.sum(TrsStatsDetect.mon),
                      func.sum(TrsStatsDetect.mon_iv),
                      func.sum(TrsStatsDetect.raid),
                      func.sum(TrsStatsDetect.quest)) \
            .select_from(TrsStatsDetect)
        where_conditions = []
        if worker:
            where_conditions.append(TrsStatsDetect.worker == worker)
        if include_last_n_minutes:
            minutes = datetime.now().replace(
                minute=0, second=0, microsecond=0) - timedelta(minutes=include_last_n_minutes)
            where_conditions.append(TrsStatsDetect.timestamp_scan >= int(minutes.now().timestamp()))
        if where_conditions:
            # Avoid empty where
            stmt = stmt.where(and_(*where_conditions))
        # Group_by needed to not cut off other workers using min function
        if hourly:
            stmt = stmt.group_by(TrsStatsDetect.worker, func.day(func.FROM_UNIXTIME(TrsStatsDetect.timestamp_scan)),
                                 func.hour(func.FROM_UNIXTIME(TrsStatsDetect.timestamp_scan)))
        else:
            stmt = stmt.group_by(TrsStatsDetect.worker)
        stmt = stmt.order_by(TrsStatsDetect.timestamp_scan)
        result = await session.execute(stmt)
        results: Dict[str, Dict[int, Tuple[int, int, int, int]]] = {}
        for hour_timestamp, worker, sum_mons, sum_iv, sum_raids, sum_quests in result:
            if worker not in results:
                results[worker] = {}
            results[worker][hour_timestamp] = (int(sum_mons), int(sum_iv), int(sum_raids), int(sum_quests))
        return results

    @staticmethod
    async def add(session: AsyncSession, worker: str, timestamp_scan: int, raid: int, mon: int,
                  mon_iv: int, quest: int) -> None:
        stat = TrsStatsDetect()
        stat.worker = worker
        stat.timestamp_scan = timestamp_scan
        stat.raid = raid
        stat.mon = mon
        stat.mon_iv = mon_iv
        stat.quest = quest
        session.add(stat)

    @staticmethod
    async def cleanup(session: AsyncSession, delete_before_timestap_scan: int) -> None:
        stmt = delete(TrsStatsDetect).where(TrsStatsDetect.timestamp_scan < delete_before_timestap_scan)
        await session.execute(stmt)
