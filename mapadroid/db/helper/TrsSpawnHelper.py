import asyncio
import concurrent
import functools
import time
from _datetime import timedelta
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Collection

from sqlalchemy import and_, update, func, or_, not_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import TrsSpawn, TrsEvent
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.utils.DatetimeWrapper import DatetimeWrapper
from mapadroid.utils.collections import Location
from mapadroid.utils.logging import LoggerEnums, get_logger

logger = get_logger(LoggerEnums.database)


# noinspection PyComparisonWithNone
class TrsSpawnHelper:
    @staticmethod
    async def get(session: AsyncSession, spawn_id: int) -> Optional[TrsSpawn]:
        stmt = select(TrsSpawn).where(TrsSpawn.spawnpoint == spawn_id)
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_all(session: AsyncSession, spawn_ids: List[int] = None) -> List[TrsSpawn]:
        stmt = select(TrsSpawn)
        if spawn_ids is not None:
            stmt = stmt.where(TrsSpawn.spawnpoint.in_(spawn_ids))
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def __get_of_area(session: AsyncSession, geofence_helper: GeofenceHelper,
                            additional_event: Optional[int], only_unknown_endtime: bool = False) -> List[TrsSpawn]:
        if not geofence_helper:
            logger.warning("No geofence helper was passed. Returning empty list of spawns.")
            return []
        min_lat, min_lon, max_lat, max_lon = geofence_helper.get_polygon_from_fence()
        event_ids: list = [1]
        if additional_event is not None:
            event_ids.append(additional_event)

        where_condition = and_(TrsSpawn.eventid.in_(event_ids),
                               TrsSpawn.latitude >= min_lat,
                               TrsSpawn.longitude >= min_lon,
                               TrsSpawn.latitude <= max_lat,
                               TrsSpawn.longitude <= max_lon)
        if only_unknown_endtime:
            where_condition = and_(TrsSpawn.calc_endminsec == None, where_condition)

        stmt = select(TrsSpawn).where(where_condition)
        result = await session.execute(stmt)
        list_of_spawns: List[TrsSpawn] = []
        for spawnpoint in result.scalars():
            if not geofence_helper.is_coord_inside_include_geofence([spawnpoint.latitude, spawnpoint.longitude]):
                continue
            list_of_spawns.append(spawnpoint)
        return list_of_spawns

    @staticmethod
    async def get_known_of_area(session: AsyncSession, geofence_helper: GeofenceHelper,
                                additional_event: Optional[int]) -> List[TrsSpawn]:
        """
        Used to be DbWrapper::get_detected_spawns.
        Fetches any spawnpoint in the given area defined by geofence_helper
        Args:
            session:
            geofence_helper:
            additional_event:

        Returns: List of spawnpoints in the area (both with known and unknown despawn time)
        """
        return await TrsSpawnHelper.__get_of_area(session, geofence_helper, additional_event)

    @staticmethod
    async def get_known_without_despawn_of_area(session: AsyncSession, geofence_helper: GeofenceHelper,
                                                additional_event: Optional[int]) -> List[TrsSpawn]:
        """
        Used to be DbWrapper::get_undetected_spawns.
        Fetches any spawnpoint in the given area defined by geofence_helper
        Args:
            session:
            geofence_helper:
            additional_event:

        Returns: List of spawnpoints in the area (with unknown despawn time)
        """
        return await TrsSpawnHelper.__get_of_area(session, geofence_helper, additional_event, only_unknown_endtime=True)

    @staticmethod
    async def convert_spawnpoints(session: AsyncSession, spawnpoint_ids: List[int], event_id: int = 1) -> None:
        stmt = update(TrsSpawn).where(TrsSpawn.spawnpoint.in_(spawnpoint_ids)).values(eventid=event_id)
        await session.execute(stmt)

    @staticmethod
    async def get_next_spawns(session: AsyncSession, geofence_helper: GeofenceHelper,
                              additional_event: Optional[int] = None,
                              limit_next_n_seconds: Optional[int] = None) -> List[Tuple[int, Location]]:
        """
        Used to be DbWrapper::retrieve_next_spawns
        Fetches the spawnpoints of which the calculated spawn time is upcoming within the next hour and converts it
        to a List of tuples consisting of (timestamp of spawn, Location)
        Args:
            limit_next_n_seconds:
            session:
            geofence_helper:
            additional_event:

        Returns:

        """
        if not geofence_helper:
            logger.warning("No geofence helper was passed. Returning empty list of spawns.")
            return []
        min_lat, min_lon, max_lat, max_lon = geofence_helper.get_polygon_from_fence()
        event_ids: list = [1]
        if additional_event is not None:
            event_ids.append(additional_event)

        stmt = select(TrsSpawn).where(and_(TrsSpawn.eventid.in_(event_ids),
                                           TrsSpawn.latitude >= min_lat,
                                           TrsSpawn.longitude >= min_lon,
                                           TrsSpawn.latitude <= max_lat,
                                           TrsSpawn.longitude <= max_lon,
                                           TrsSpawn.calc_endminsec != None))
        result = await session.execute(stmt)
        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            next_up = await loop.run_in_executor(
                pool, functools.partial(TrsSpawnHelper.__process_next_to_encounter, result=result,
                                        geofence_helper=geofence_helper,
                                        limit_next_n_seconds=limit_next_n_seconds))

        return next_up

    @staticmethod
    def __process_next_to_encounter(result, geofence_helper=None,
                                    limit_next_n_seconds: Optional[int] = None) -> List[Tuple[int, Location]]:
        next_up: List[Tuple[int, Location]] = []
        current_time = time.time()
        current_time_of_day = DatetimeWrapper.now().replace(microsecond=0)
        timedelta_to_be_added = timedelta(hours=1)

        for spawn in result.scalars():
            if not geofence_helper.is_coord_inside_include_geofence([spawn.latitude, spawn.longitude]):
                continue
            endminsec_split = spawn.calc_endminsec.split(":")
            minutes = int(endminsec_split[0])
            seconds = int(endminsec_split[1])
            temp_date = current_time_of_day.replace(
                minute=minutes, second=seconds)
            if minutes < current_time_of_day.minute:
                # Add an hour to have the next spawn at the following hour respectively
                temp_date = temp_date + timedelta_to_be_added

            if (temp_date < current_time_of_day or limit_next_n_seconds
                    and temp_date > current_time_of_day + timedelta(seconds=limit_next_n_seconds)):
                # spawn has already happened, we should've added it in the past, let's move on
                # TODO: consider crosschecking against current mons...
                continue
            spawn_duration_minutes = 60 if spawn.spawndef == 15 else 30

            timestamp = time.mktime(temp_date.timetuple()) - spawn_duration_minutes * 60
            # check if we calculated a time in the past, if so, add an hour to it...
            timestamp = timestamp + 60 * 60 if timestamp < current_time else timestamp
            next_up.append((int(timestamp), Location(float(spawn.latitude), float(spawn.longitude))))
        return next_up

    @staticmethod
    async def download_spawns(session: AsyncSession,
                              ne_corner: Optional[Location] = None, sw_corner: Optional[Location] = None,
                              old_ne_corner: Optional[Location] = None, old_sw_corner: Optional[Location] = None,
                              timestamp: Optional[int] = None, fence: Optional[str] = None,
                              event_id: Optional[int] = None, today_only: bool = False,
                              older_than_x_days: Optional[int] = None) -> Dict[int, Tuple[TrsSpawn, TrsEvent]]:
        stmt = select(TrsSpawn, TrsEvent) \
            .join(TrsEvent, TrsEvent.id == TrsSpawn.eventid, isouter=False)
        where_conditions = []

        if (ne_corner and sw_corner
                and ne_corner.lat and ne_corner.lng and sw_corner.lat and sw_corner.lng):
            where_conditions.append(and_(TrsSpawn.latitude >= sw_corner.lat,
                                         TrsSpawn.longitude >= sw_corner.lng,
                                         TrsSpawn.latitude <= ne_corner.lat,
                                         TrsSpawn.longitude <= ne_corner.lng))
        if (old_ne_corner and old_sw_corner
                and old_ne_corner.lat and old_ne_corner.lng and old_sw_corner.lat and old_sw_corner.lng):
            where_conditions.append(and_(TrsSpawn.latitude >= old_sw_corner.lat,
                                         TrsSpawn.longitude >= old_sw_corner.lng,
                                         TrsSpawn.latitude <= old_ne_corner.lat,
                                         TrsSpawn.longitude <= old_ne_corner.lng))
        if timestamp:
            where_conditions.append(TrsSpawn.last_scanned >= DatetimeWrapper.fromtimestamp(timestamp))

        if fence:
            polygon = "POLYGON(({}))".format(fence)
            where_conditions.append(func.ST_Contains(func.ST_GeomFromText(polygon),
                                                     func.POINT(TrsSpawn.latitude, TrsSpawn.longitude)))
        if event_id:
            where_conditions.append(TrsSpawn.eventid == event_id)
        if today_only:
            where_conditions.append(or_(DatetimeWrapper.now().today() <= TrsSpawn.last_scanned,
                                        DatetimeWrapper.now().today() <= TrsSpawn.last_non_scanned))
        elif older_than_x_days:
            # elif as it makes no sense to check for older than X days AND today
            older_than_date: datetime = DatetimeWrapper.now().today() - timedelta(days=older_than_x_days)
            where_conditions.append(or_(older_than_date <= TrsSpawn.last_scanned,
                                        older_than_date <= TrsSpawn.last_non_scanned))
        stmt = stmt.where(and_(*where_conditions))
        result = await session.execute(stmt)
        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            spawns = await loop.run_in_executor(
                pool, TrsSpawnHelper.__transform_result, result)

        return spawns

    @staticmethod
    def __transform_result(result):
        result_full = result.all()
        spawns: Dict[int, Tuple[TrsSpawn, TrsEvent]] = {}
        for (spawn, event) in result_full:
            spawns[spawn.spawnpoint] = (spawn, event)
        return spawns

    @staticmethod
    async def get_all_spawnpoints_count(session: AsyncSession) -> int:
        """
        DbStatsReader::get_all_spawnpoints_count
        Args:
            session:

        Returns: amount of all spawnpoints known

        """
        stmt = select(func.COUNT("*")) \
            .select_from(TrsSpawn)
        result = await session.execute(stmt)
        return result.scalar()

    @staticmethod
    async def delete_all_except(session: AsyncSession, spawns: Collection[int]) -> None:
        stmt = delete(TrsSpawn).where(not_(TrsSpawn.spawnpoint.in_(spawns)))
        await session.execute(stmt)
