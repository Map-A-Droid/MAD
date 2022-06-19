from datetime import timedelta
from typing import Dict, Optional, Tuple

from sqlalchemy import and_, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import TrsStatsLocation
from mapadroid.utils.DatetimeWrapper import DatetimeWrapper


class TrsStatsLocationHelper:
    @staticmethod
    async def get_locations(session: AsyncSession, include_last_n_minutes: Optional[int] = None,
                            hourly: bool = True,
                            worker: Optional[str] = None) -> Dict[str, Dict[int, Tuple[int, int, int]]]:
        """
        Used to be DbStatsReader::get_locations
        Fetches { worker : { timestamp_hour : (location_count, locations_ok, locations_nok)}}
        Args:
            session:
            include_last_n_minutes:
            hourly:
            worker:

        Returns:

        """
        stmt = select(func.unix_timestamp(
            func.DATE_FORMAT(func.from_unixtime(func.min(TrsStatsLocation.timestamp_scan)), '%y-%m-%d %k:00:00')),
            TrsStatsLocation.worker,
            func.sum(TrsStatsLocation.location_ok),
            func.sum(TrsStatsLocation.location_nok)) \
            .select_from(TrsStatsLocation)
        where_conditions = []
        if worker:
            where_conditions.append(TrsStatsLocation.worker == worker)
        if include_last_n_minutes:
            minutes = DatetimeWrapper.now().replace(
                minute=0, second=0, microsecond=0) - timedelta(minutes=include_last_n_minutes)
            where_conditions.append(TrsStatsLocation.timestamp_scan >= int(minutes.timestamp()))
        if where_conditions:
            stmt = stmt.where(and_(*where_conditions))
        # Group_by needed to not cut off other workers using min function
        if hourly:
            stmt = stmt.group_by(TrsStatsLocation.worker, func.day(func.FROM_UNIXTIME(TrsStatsLocation.timestamp_scan)),
                                 func.hour(func.FROM_UNIXTIME(TrsStatsLocation.timestamp_scan)))
        else:
            stmt = stmt.group_by(TrsStatsLocation.worker)
        result = await session.execute(stmt)
        results: Dict[str, Dict[int, Tuple[int, int, int]]] = {}
        for hour_timestamp, worker, locations_ok, locations_nok in result:
            if worker not in results:
                results[worker] = {}
            location_count: int = locations_nok + locations_ok
            results[worker][hour_timestamp] = (int(location_count), int(locations_ok), int(locations_nok))
        return results

    @staticmethod
    async def get_location_info(session: AsyncSession) -> Dict[str, Tuple[int, int, int, float]]:
        """
        DbStatsReader::get_location_info
        Fetches stats per worker:
        Dict[worker, Tuple[sum_location_count, sum_location_ok, sum_location_not_ok, percentage_nok_as_failure_rate]]
        Args:
            session:

        Returns:

        """
        stmt = select(TrsStatsLocation.worker,
                      func.sum(TrsStatsLocation.location_ok),
                      func.sum(TrsStatsLocation.location_nok)) \
            .select_from(TrsStatsLocation) \
            .group_by(TrsStatsLocation.worker)
        result = await session.execute(stmt)
        results: Dict[str, Tuple[int, int, int, float]] = {}
        for worker, location_ok, location_nok in result:
            location_count: int = location_ok + location_nok
            if location_count > 0:
                failure_rate = int(location_nok) / int(location_count) * 100
            else:
                failure_rate = 0
            results[worker] = (int(location_count), int(location_ok), int(location_nok), failure_rate)
        return results

    @staticmethod
    async def add(session: AsyncSession, worker: str, timestamp_scan: int, location_ok: int,
                  location_nok: int) -> None:
        stat = TrsStatsLocation()
        stat.worker = worker
        stat.timestamp_scan = timestamp_scan
        stat.location_ok = location_ok
        stat.location_nok = location_nok
        session.add(stat)

    @staticmethod
    async def cleanup(session: AsyncSession, delete_before_timestap_scan: int) -> None:
        stmt = delete(TrsStatsLocation).where(TrsStatsLocation.timestamp_scan < delete_before_timestap_scan)
        await session.execute(stmt)
