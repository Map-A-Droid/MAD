from datetime import timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, asc, case, delete, desc, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import aliased

from mapadroid.db.model import TrsStatsLocationRaw
from mapadroid.utils.collections import Location
from mapadroid.utils.DatetimeWrapper import DatetimeWrapper
from mapadroid.utils.madGlobals import PositionType, TransportType
from mapadroid.worker.WorkerType import WorkerType


class TrsStatsLocationRawHelper:
    @staticmethod
    async def get_avg_data_time(session: AsyncSession, include_last_n_minutes: Optional[int] = None,
                                hourly: bool = True,
                                worker: Optional[str] = None) -> Dict[
        str, Dict[int, List[Tuple[str, int, float, str]]]]:
        """
        Fetches { worker : { timestamp_hour : [transport_type, locations_with_data, avg data receiving time, walker_type]}}
        Args:
            session:
            include_last_n_minutes:
            hourly:
            worker:

        Returns:

        """
        stmt = select(func.unix_timestamp(
            func.DATE_FORMAT(func.from_unixtime(func.min(TrsStatsLocationRaw.period)), '%y-%m-%d %k:00:00')),
            TrsStatsLocationRaw.transporttype,
            TrsStatsLocationRaw.worker,
            func.count(TrsStatsLocationRaw.fix_ts),
            func.avg(TrsStatsLocationRaw.data_ts - TrsStatsLocationRaw.fix_ts),
            TrsStatsLocationRaw.walker) \
            .select_from(TrsStatsLocationRaw)
        where_conditions = [TrsStatsLocationRaw.success == 1,
                            TrsStatsLocationRaw.type.in_([0, 1]),
                            or_(TrsStatsLocationRaw.walker == WorkerType.MON_MITM.value,
                                TrsStatsLocationRaw.walker == WorkerType.IV_MITM.value,
                                TrsStatsLocationRaw.walker == WorkerType.STOPS.value)]
        if worker:
            where_conditions.append(TrsStatsLocationRaw.worker == worker)
        if include_last_n_minutes:
            minutes = DatetimeWrapper.now().replace(
                minute=0, second=0, microsecond=0) - timedelta(minutes=include_last_n_minutes)
            where_conditions.append(TrsStatsLocationRaw.period >= int(minutes.timestamp()))
        stmt = stmt.where(and_(*where_conditions))
        # Group_by needed to not cut off other workers using min function
        if hourly:
            stmt = stmt.group_by(TrsStatsLocationRaw.worker, func.day(func.FROM_UNIXTIME(TrsStatsLocationRaw.period)),
                                 func.hour(func.FROM_UNIXTIME(TrsStatsLocationRaw.period)),
                                 TrsStatsLocationRaw.transporttype, TrsStatsLocationRaw.walker)
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
            results[worker][hour_timestamp].append(
                (transport_type_readable, count_of_fix_ts, float(avg_data_ts), walker))
        return results

    @staticmethod
    async def get_locations_dataratio(session: AsyncSession, include_last_n_minutes: Optional[int] = None,
                                      grouped: bool = True,
                                      worker: Optional[str] = None) -> Dict[
        str, Dict[int, List[Tuple[int, int, int, str]]]]:
        """
        Used to be DbStatsReader::get_locations_dataratio
        Fetches { worker : { timestamp_hour : [Tuple(count_period, location_type, success, success_locationtype_readable)]}}
        Args:
            session:
            include_last_n_minutes:
            grouped:
            worker:

        Returns:

        """
        # TODO
        stmt = select(func.unix_timestamp(
            func.DATE_FORMAT(func.from_unixtime(func.min(TrsStatsLocationRaw.period)), '%y-%m-%d %k:00:00')),
            TrsStatsLocationRaw.worker,
            func.count(TrsStatsLocationRaw.period),
            TrsStatsLocationRaw.type,
            TrsStatsLocationRaw.success) \
            .select_from(TrsStatsLocationRaw)
        where_conditions = [TrsStatsLocationRaw.type.in_([0, 1])]
        if worker:
            where_conditions.append(TrsStatsLocationRaw.worker == worker)
        if include_last_n_minutes:
            minutes = DatetimeWrapper.now().replace(
                minute=0, second=0, microsecond=0) - timedelta(minutes=include_last_n_minutes)
            where_conditions.append(TrsStatsLocationRaw.period >= int(minutes.timestamp()))
        stmt = stmt.where(and_(*where_conditions))
        # Group_by needed to not cut off other workers using min function
        if grouped:
            stmt = stmt.group_by(TrsStatsLocationRaw.worker,
                                 TrsStatsLocationRaw.success,
                                 TrsStatsLocationRaw.type)
        else:
            stmt = stmt.group_by(TrsStatsLocationRaw.worker)
        result = await session.execute(stmt)
        results: Dict[str, Dict[int, List[Tuple[int, int, int, str]]]] = {}
        for hour_timestamp, worker, count_period, location_type, success in result:
            if worker not in results:
                results[worker] = {}
            if hour_timestamp not in results[worker]:
                results[worker][hour_timestamp] = []
            # TODO: Rather use enum
            written_type: str = ""
            if location_type == 0:
                if success == 1:
                    written_type = "OK-Normal"
                else:
                    written_type = "NOK-Normal"
            else:
                if success == 1:
                    written_type = "OK-PrioQ"
                else:
                    written_type = "NOK-PrioQ"
            results[worker][hour_timestamp].append((int(count_period), int(location_type), int(success), written_type))
        return results

    @staticmethod
    async def get_all_empty_scans(session: AsyncSession) -> List[Tuple[int, Location, str, str, int, int]]:
        """
        DbStatsReader::get_all_empty_scans
        Fetches List of tuples containing (count_of_empty_scans, Location(lat,lng), workers_affected, type_as_str, last_scan_timestamp_epoch, successful_scans)
        Args:
            session:

        Returns:

        """
        alias_b = aliased(TrsStatsLocationRaw)
        alias_c = aliased(TrsStatsLocationRaw)
        successcount = select(func.count(alias_c.id)) \
            .select_from(alias_c) \
            .where(and_(alias_b.lat == alias_c.lat,
                        alias_b.lng == alias_c.lng,
                        alias_c.success == 1)) \
            .label("successcount")

        stmt = select(func.count(alias_b.id),
                      alias_b.lat,
                      alias_b.lng,
                      func.group_concat(alias_b.worker.distinct()),
                      func.IF(alias_b.type == 0, "Normal", "PrioQ"),
                      func.max(alias_b.period),
                      successcount
                      ) \
            .select_from(alias_b) \
            .where(alias_b.success == 0) \
            .group_by(alias_b.lat, alias_b.lng, alias_b.type) \
            .having(and_(func.count() > 5, successcount == 0)) \
            .order_by(desc(func.count(alias_b.id)))
        result = await session.execute(stmt)
        empty_scans: List[Tuple[int, Location, str, str, int, int]] = []
        for count, lat, lng, workers_affected, route_type, last_scan, successes in result:
            empty_scans.append((count, Location(float(lat), float(lng)), workers_affected, route_type, last_scan,
                                successes))
        return empty_scans

    @staticmethod
    async def get_location_raw(session: AsyncSession,
                               include_last_n_minutes: Optional[int] = None,
                               worker: Optional[str] = None) -> List[Tuple[Location, str, str, int, int, str]]:
        """
        DbStatsReader::get_location_raw
        Fetches List of tuples containing (Location(lat,lng), location_type_as_str, success_as_str, timestamp_fix,
        timestamp_data_or_fix, transporttype_as_str)
        Args:
            worker:
            include_last_n_minutes:
            session:

        Returns:

        """
        stmt = select(TrsStatsLocationRaw.lat,
                      TrsStatsLocationRaw.lng,
                      case((TrsStatsLocationRaw.type == 0, "Normal"),
                           (TrsStatsLocationRaw.type == 1, "PrioQ"),
                           (TrsStatsLocationRaw.type == 2, "Startup"),
                           (TrsStatsLocationRaw.type == 3, "Reboot"),
                           else_="Restart"),
                      func.IF(TrsStatsLocationRaw.success == 1, "OK", "NOK"),
                      TrsStatsLocationRaw.fix_ts,
                      func.IF(TrsStatsLocationRaw.data_ts == 0, TrsStatsLocationRaw.fix_ts,
                              TrsStatsLocationRaw.data_ts),
                      case((TrsStatsLocationRaw.transporttype == TransportType.TELEPORT.value, "Teleport"),
                           (TrsStatsLocationRaw.transporttype == TransportType.WALK.value, "Walk"),
                           else_="other"),
                      ) \
            .select_from(TrsStatsLocationRaw)

        where_conditions = []
        if worker:
            where_conditions.append(TrsStatsLocationRaw.worker == worker)
        if include_last_n_minutes:
            minutes = DatetimeWrapper.now().replace(
                minute=0, second=0, microsecond=0) - timedelta(minutes=include_last_n_minutes)
            where_conditions.append(TrsStatsLocationRaw.period >= int(minutes.timestamp()))
        stmt = stmt.where(and_(*where_conditions))
        stmt = stmt.order_by(asc(TrsStatsLocationRaw.id))
        result = await session.execute(stmt)
        locations: List[Tuple[Location, str, str, int, int, str]] = []
        for lat, lng, location_type, success, fix_timestamp, data_fix_timestamp, transporttype in result:
            locations.append((Location(float(lat), float(lng)), location_type, success, int(fix_timestamp),
                              int(data_fix_timestamp), transporttype))
        return locations

    @staticmethod
    async def add(session: AsyncSession, worker: str, fix_timestamp: int, location: Location, data_timestamp: int,
                  type_of_location: PositionType, walker: str, success: bool, period: int,
                  transporttype: TransportType):
        stat = TrsStatsLocationRaw()
        stat.worker = worker
        stat.fix_ts = fix_timestamp
        stat.lat = location.lat
        stat.lng = location.lng
        stat.data_ts = data_timestamp
        stat.type = type_of_location.value
        stat.walker = walker
        stat.success = 1 if success else 0
        stat.period = period
        stat.transporttype = transporttype.value
        session.add(stat)

    @staticmethod
    async def get(session: AsyncSession, worker: str, location: Location, type_of_location: PositionType,
                  period: int) -> Optional[TrsStatsLocationRaw]:
        stmt = select(TrsStatsLocationRaw).where(and_(TrsStatsLocationRaw.worker == worker,
                                                      TrsStatsLocationRaw.lat == location.lat,
                                                      TrsStatsLocationRaw.lng == location.lng,
                                                      TrsStatsLocationRaw.type == type_of_location.value,
                                                      TrsStatsLocationRaw.period == period
                                                      ))
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def cleanup(session: AsyncSession, delete_before_timestap_scan: int) -> None:
        stmt = delete(TrsStatsLocationRaw).where(TrsStatsLocationRaw.period < delete_before_timestap_scan)
        await session.execute(stmt)
