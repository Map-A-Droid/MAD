from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

from sqlalchemy import and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import TrsStatsLocation


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
        stmt = select(func.unix_timestamp(func.DATE_FORMAT(func.from_unixtime(func.min(TrsStatsLocation.timestamp_scan)), '%y-%m-%d %k:00:00')),
                      TrsStatsLocation.worker,
                      func.sum(TrsStatsLocation.location_count),
                      func.sum(TrsStatsLocation.location_ok),
                      func.sum(TrsStatsLocation.location_nok))\
            .select_from(TrsStatsLocation)
        where_conditions = []
        if worker:
            where_conditions.append(TrsStatsLocation.worker == worker)
        if include_last_n_minutes:
            minutes = datetime.utcnow().replace(
                minute=0, second=0, microsecond=0) - timedelta(minutes=include_last_n_minutes)
            where_conditions.append(TrsStatsLocation.timestamp_scan >= int(minutes.utcnow().timestamp()))
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
        for hour_timestamp, worker, location_count, locations_ok, locations_nok in result:
            if worker not in results:
                results[worker] = {}

            results[worker][hour_timestamp] = (int(location_count), int(locations_ok), int(locations_nok))
        return results
