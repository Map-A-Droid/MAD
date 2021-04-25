from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import TrsStatsLocationRaw
from mapadroid.worker.WorkerType import WorkerType


class TrsStatsLocationRawHelper:
    @staticmethod
    async def get_avg_data_time(session: AsyncSession, include_last_n_minutes: Optional[int] = None,
                                             hourly: bool = True,
                                             worker: Optional[str] = None) -> Dict[str, Dict[int, List[Tuple[str, int, float, str]]]]:
        """
        Fetches { worker : { timestamp_hour : [transport_type, locations_with_data, avg data receiving time, walker_type]}}
        Args:
            session:
            include_last_n_minutes:
            hourly:
            worker:

        Returns:

        """
        stmt = select(func.unix_timestamp(func.DATE_FORMAT(func.from_unixtime(func.min(TrsStatsLocationRaw.period)), '%y-%m-%d %k:00:00')),
                      TrsStatsLocationRaw.transporttype,
                      TrsStatsLocationRaw.worker,
                      func.count(TrsStatsLocationRaw.fix_ts),
                      func.avg(TrsStatsLocationRaw.data_ts - TrsStatsLocationRaw.fix_ts),
                      TrsStatsLocationRaw.walker)\
            .select_from(TrsStatsLocationRaw)
        where_conditions = [TrsStatsLocationRaw.success == 1,
                            TrsStatsLocationRaw.type.in_([0, 1]),
                            or_(TrsStatsLocationRaw.walker == WorkerType.MON_MITM.value,
                                TrsStatsLocationRaw.walker == WorkerType.IV_MITM.value,
                                TrsStatsLocationRaw.walker == WorkerType.STOPS.value)]
        if worker:
            where_conditions.append(TrsStatsLocationRaw.worker == worker)
        if include_last_n_minutes:
            minutes = datetime.utcnow().replace(
                minute=0, second=0, microsecond=0) - timedelta(minutes=include_last_n_minutes)
            where_conditions.append(TrsStatsLocationRaw.period >= int(minutes.utcnow().timestamp()))
        stmt = stmt.where(and_(*where_conditions))
        # Group_by needed to not cut off other workers using min function
        if hourly:
            stmt = stmt.group_by(TrsStatsLocationRaw.worker, func.day(func.FROM_UNIXTIME(TrsStatsLocationRaw.period)),
                                 func.hour(func.FROM_UNIXTIME(TrsStatsLocationRaw.period)),
                                 TrsStatsLocationRaw.transporttype)
        else:
            stmt = stmt.group_by(TrsStatsLocationRaw.worker)
        result = await session.execute(stmt)
        results: Dict[str, Dict[int, List[Tuple[str, int, float, str]]]] = {}
        for hour_timestamp, transport_type, worker, count_of_fix_ts, avg_data_ts, walker in result:
            if worker not in results:
                results[worker] = {}
            if hour_timestamp not in results[worker]:
                results[worker][hour_timestamp] = []
            transport_type_readable: str = "other"
            if transport_type == 0:
                transport_type_readable = "Teleport"
            elif transport_type == 1:
                transport_type_readable = "Walk"
            results[worker][hour_timestamp].append((transport_type_readable, count_of_fix_ts, float(avg_data_ts), walker))
        return results

    @staticmethod
    async def get_locations_dataratio(session: AsyncSession, include_last_n_minutes: Optional[int] = None,
                                             grouped: bool = True,
                                             worker: Optional[str] = None) -> Dict[str, Dict[int, List[Tuple[str, int, float, str]]]]:
        """
        Used to be DbStatsReader::get_locations_dataratio
        Fetches { worker : { timestamp_hour : [transport_type, locations_with_data, avg data receiving time, walker_type]}}
        Args:
            session:
            include_last_n_minutes:
            grouped:
            worker:

        Returns:

        """
        # TODO
        stmt = select(func.unix_timestamp(func.DATE_FORMAT(func.from_unixtime(func.min(TrsStatsLocationRaw.period)), '%y-%m-%d %k:00:00')),
                      TrsStatsLocationRaw.transporttype,
                      TrsStatsLocationRaw.worker,
                      func.count(TrsStatsLocationRaw.fix_ts),
                      func.avg(TrsStatsLocationRaw.data_ts - TrsStatsLocationRaw.fix_ts),
                      TrsStatsLocationRaw.walker)\
            .select_from(TrsStatsLocationRaw)
        where_conditions = [TrsStatsLocationRaw.success == 1,
                            TrsStatsLocationRaw.type.in_([0, 1]),
                            or_(TrsStatsLocationRaw.walker == WorkerType.MON_MITM.value,
                                TrsStatsLocationRaw.walker == WorkerType.IV_MITM.value,
                                TrsStatsLocationRaw.walker == WorkerType.STOPS.value)]
        if worker:
            where_conditions.append(TrsStatsLocationRaw.worker == worker)
        if include_last_n_minutes:
            minutes = datetime.utcnow().replace(
                minute=0, second=0, microsecond=0) - timedelta(minutes=include_last_n_minutes)
            where_conditions.append(TrsStatsLocationRaw.period >= int(minutes.utcnow().timestamp()))
        stmt = stmt.where(and_(*where_conditions))
        # Group_by needed to not cut off other workers using min function
        if grouped:
            stmt = stmt.group_by(TrsStatsLocationRaw.worker,
                                 TrsStatsLocationRaw.success,
                                 TrsStatsLocationRaw.type)
        else:
            stmt = stmt.group_by(TrsStatsLocationRaw.worker)
        result = await session.execute(stmt)
        results: Dict[str, Dict[int, List[Tuple[str, int, float, str]]]] = {}
        for hour_timestamp, transport_type, worker, count_of_fix_ts, avg_data_ts, walker in result:
            if worker not in results:
                results[worker] = {}
            if hour_timestamp not in results[worker]:
                results[worker][hour_timestamp] = []
            transport_type_readable: str = "other"
            if transport_type == 0:
                transport_type_readable = "Teleport"
            elif transport_type == 1:
                transport_type_readable = "Walk"
            results[worker][hour_timestamp].append((transport_type_readable, count_of_fix_ts, float(avg_data_ts), walker))
        return results
