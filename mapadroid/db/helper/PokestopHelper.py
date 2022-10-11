from datetime import datetime
from operator import or_
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import Pokestop, TrsQuest, TrsVisited
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.utils.collections import Location
from mapadroid.utils.DatetimeWrapper import DatetimeWrapper
from mapadroid.utils.logging import LoggerEnums, get_logger
from mapadroid.utils.madGlobals import QuestLayer
from mapadroid.utils.timezone_util import get_timezone_at

logger = get_logger(LoggerEnums.database)


# noinspection PyComparisonWithNone
class PokestopHelper:
    @staticmethod
    async def get(session: AsyncSession, pokestop_id: str) -> Optional[Pokestop]:
        stmt = select(Pokestop).where(Pokestop.pokestop_id == pokestop_id)
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_at_location(session: AsyncSession, location: Location) -> Optional[Pokestop]:
        stmt = select(Pokestop).where(and_(Pokestop.latitude == location.lat,
                                           Pokestop.longitude == location.lng))
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_locations_in_fence(session: AsyncSession, geofence_helper: Optional[GeofenceHelper] = None,
                                     fence: Optional[Tuple[str, Optional[GeofenceHelper]]] = None) -> List[Location]:
        min_lat, min_lon, max_lat, max_lon = -90, -180, 90, 180
        if geofence_helper:
            min_lat, min_lon, max_lat, max_lon = geofence_helper.get_polygon_from_fence()
        stmt = select(Pokestop)
        where_and_clauses = [Pokestop.latitude >= min_lat,
                             Pokestop.longitude >= min_lon,
                             Pokestop.latitude <= max_lat,
                             Pokestop.longitude <= max_lon]
        if fence:
            fence_str, _ = fence
            polygon = "POLYGON(({}))".format(fence_str)
            where_and_clauses.append(func.ST_Contains(func.ST_GeomFromText(polygon),
                                                      func.POINT(Pokestop.latitude, Pokestop.longitude)))

        stmt = stmt.where(and_(*where_and_clauses))
        result = await session.execute(stmt)
        list_of_coords: List[Location] = []
        for pokestop in result.scalars().all():
            list_of_coords.append(Location(float(pokestop.latitude), float(pokestop.longitude)))
        if geofence_helper:
            return geofence_helper.get_geofenced_coordinates(list_of_coords)
        else:
            return list_of_coords

    @staticmethod
    async def any_stops_unvisited(session: AsyncSession, geofence_helper: GeofenceHelper, origin: str) -> bool:
        return len(await PokestopHelper.stops_not_visited(session, geofence_helper, origin)) > 0

    @staticmethod
    async def stops_not_visited(session: AsyncSession, geofence_helper: GeofenceHelper, origin: str) -> List[Pokestop]:
        """
        stops_from_db_unvisited
        Args:
            session:
            geofence_helper:
            origin:

        Returns:

        """
        logger.debug3("DbWrapper::any_stops_unvisited called")
        min_lat, min_lon, max_lat, max_lon = geofence_helper.get_polygon_from_fence()
        stmt = select(Pokestop) \
            .join(TrsVisited, and_(Pokestop.pokestop_id == TrsVisited.pokestop_id,
                                   TrsVisited.origin == origin), isouter=True) \
            .where(and_(Pokestop.latitude >= min_lat, Pokestop.longitude >= min_lon,
                        Pokestop.latitude <= max_lat, Pokestop.longitude <= max_lon,
                        TrsVisited.origin == None))
        result = await session.execute(stmt)
        unvisited: List[Pokestop] = []
        for pokestop in result.scalars().all():
            if geofence_helper.is_coord_inside_include_geofence([pokestop.latitude, pokestop.longitude]):
                unvisited.append(pokestop)
        return unvisited

    @staticmethod
    async def update_location(session: AsyncSession, fort_id: str, location: Location) -> None:
        pokestop: Optional[Pokestop] = await PokestopHelper.get(session, fort_id)
        if not pokestop:
            return
        pokestop.latitude = location.lat
        pokestop.longitude = location.lng
        session.add(pokestop)

    @staticmethod
    async def delete(session: AsyncSession, location: Location) -> None:
        pokestop: Optional[Pokestop] = await PokestopHelper.get_at_location(session, location)
        if pokestop:
            await session.delete(pokestop)

    @staticmethod
    async def get_nearby(session: AsyncSession, location: Location, max_distance: int = 0.5) -> Dict[str, Pokestop]:
        """
        DbWrapper::get_stop_ids_and_locations_nearby
        Args:
            session:
            location:
            max_distance:

        Returns:

        """
        if max_distance < 0:
            logger.warning("Cannot search for stops at negative range...")
            return {}

        stmt = select(Pokestop).where(func.sqrt(func.pow(69.1 * (Pokestop.latitude - location.lat), 2)
                                                + func.pow(69.1 * (location.lng - Pokestop.longitude), 2))
                                      <= max_distance)
        result = await session.execute(stmt)
        stops: Dict[str, Pokestop] = {}
        for pokestop in result.scalars().all():
            stops[pokestop.pokestop_id] = pokestop
        return stops

    @staticmethod
    async def get_nearby_increasing_range_within_area(session: AsyncSession,
                                                      geofence_helper: GeofenceHelper, origin: str, location: Location,
                                                      limit: int = 20, ignore_spinned: bool = True,
                                                      max_distance: int = 1) -> List[Pokestop]:
        """
        DbWrapper::get_nearest_stops_from_position
        Args:
            session:
            geofence_helper:
            origin:
            location: Location to be used for the search of nearby stops
            limit: Limiting amount of stops returned
            ignore_spinned: Ignore stops that have been spun by the origin
            max_distance:

        Returns:

        """
        logger.debug3("DbWrapper::get_nearest_stops_from_position called")
        min_lat, min_lon, max_lat, max_lon = geofence_helper.get_polygon_from_fence()

        stops_retrieved: List[Pokestop] = []
        select()
        iteration: int = 0
        while (limit > 0 and len(stops_retrieved) < limit) and iteration < 10:
            iteration += 1
            stops_retrieved.clear()
            where_condition = and_(Pokestop.latitude >= min_lat, Pokestop.longitude >= min_lon,
                                   Pokestop.latitude <= max_lat, Pokestop.longitude <= max_lon,
                                   func.sqrt(func.pow(69.1 * (Pokestop.latitude - location.lat), 2)
                                             + func.pow(69.1 * (location.lng - Pokestop.longitude), 2)) <= max_distance
                                   )
            if ignore_spinned:
                where_condition = and_(TrsVisited.origin == None, where_condition)

            stmt = select(Pokestop,
                          func.sqrt(func.pow(69.1 * (Pokestop.latitude - location.lat), 2)
                                    + func.pow(69.1 * (location.lng - Pokestop.longitude), 2)).label("distance")) \
                .select_from(Pokestop) \
                .join(TrsVisited, and_(Pokestop.pokestop_id == TrsVisited.pokestop_id,
                                       TrsVisited.origin == origin), isouter=True) \
                .where(where_condition).order_by("distance")
            if limit > 0:
                stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            for stop, _distance in result.all():
                if not geofence_helper.is_coord_inside_include_geofence([stop.latitude, stop.longitude]):
                    continue
                stops_retrieved.append(stop)

            if len(stops_retrieved) == 0 or limit > 0 and len(stops_retrieved) <= limit:
                logger.debug("No location found or not getting enough locations - increasing distance")
                if iteration >= 7:
                    # setting middle of fence as new startposition
                    lat, lon = geofence_helper.get_middle_from_fence()
                    location = Location(lat, lon)
                else:
                    max_distance += 3
            else:
                # Retrieved some stops (or hit the limit...)
                max_distance += 2
        return stops_retrieved

    @staticmethod
    async def get_with_quests(session: AsyncSession,
                              ne_corner: Optional[Location] = None, sw_corner: Optional[Location] = None,
                              old_ne_corner: Optional[Location] = None, old_sw_corner: Optional[Location] = None,
                              timestamp: Optional[int] = None,
                              fence: Optional[Tuple[str, Optional[GeofenceHelper]]] = None) -> \
            Dict[int, Tuple[Pokestop, Dict[int, TrsQuest]]]:
        """
        quests_from_db
        Args:
            session:
            ne_corner:
            sw_corner:
            old_ne_corner:
            old_sw_corner:
            timestamp:
            fence:

        Returns:

        """
        # TODO: Check that a stop is returned multiple times
        stmt = select(Pokestop, TrsQuest) \
            .join(TrsQuest, TrsQuest.GUID == Pokestop.pokestop_id, isouter=True)
        where_conditions = []
        # Fetch the middle of the boundary coords if passed, otherwise just default to local time of MAD
        applicable_midnight: datetime
        if fence:
            fence_str, geofence_helper = fence
            lat, lon = geofence_helper.get_middle_from_fence()
            relevant_timezone: datetime.tzinfo = get_timezone_at(Location(lat, lon))
            applicable_midnight = datetime.now(tz=relevant_timezone)
        elif ne_corner and sw_corner and ne_corner.lat and ne_corner.lng and sw_corner.lat and sw_corner.lng:
            # Roughly the middle...
            lat = (ne_corner.lat + sw_corner.lat) / 2
            lon = (ne_corner.lng + sw_corner.lng) / 2
            relevant_timezone: datetime.tzinfo = get_timezone_at(Location(lat, lon))
            applicable_midnight = datetime.now(tz=relevant_timezone)
        else:
            applicable_midnight = datetime.today()
        applicable_midnight = applicable_midnight.replace(hour=0, minute=0, second=0, microsecond=0)
        where_conditions.append(TrsQuest.quest_timestamp > applicable_midnight.timestamp())

        if ne_corner and sw_corner and ne_corner.lat and ne_corner.lng and sw_corner.lat and sw_corner.lng:
            where_conditions.append(and_(Pokestop.latitude >= sw_corner.lat,
                                         Pokestop.longitude >= sw_corner.lng,
                                         Pokestop.latitude <= ne_corner.lat,
                                         Pokestop.longitude <= ne_corner.lng))
        if (old_ne_corner and old_sw_corner
                and old_ne_corner.lat and old_ne_corner.lng and old_sw_corner.lat and old_sw_corner.lng):
            where_conditions.append(and_(Pokestop.latitude >= old_sw_corner.lat,
                                         Pokestop.longitude >= old_sw_corner.lng,
                                         Pokestop.latitude <= old_ne_corner.lat,
                                         Pokestop.longitude <= old_ne_corner.lng))
        if timestamp:
            where_conditions.append(TrsQuest.quest_timestamp >= timestamp)

        if fence:
            fence_str, geofence_helper = fence
            polygon = "POLYGON(({}))".format(fence_str)
            where_conditions.append(func.ST_Contains(func.ST_GeomFromText(polygon),
                                                     func.POINT(Pokestop.latitude, Pokestop.longitude)))
        stmt = stmt.where(and_(*where_conditions))
        result = await session.execute(stmt)
        stop_with_quest: Dict[int, Tuple[Pokestop, Dict[int, TrsQuest]]] = {}
        for (stop, quest) in result.all():
            if stop.pokestop_id not in stop_with_quest:
                stop_with_quest[stop.pokestop_id] = (stop, {})
            stop_with_quest[stop.pokestop_id][1][quest.layer] = quest
        return stop_with_quest

    @staticmethod
    async def get_without_quests(session: AsyncSession,
                                 geofence_helper: GeofenceHelper,
                                 quest_layer: QuestLayer) -> Dict[int, Pokestop]:
        """
        stop_from_db_without_quests
        Args:
            quest_layer:
            geofence_helper:
            session:

        Returns:

        """
        stmt = select(Pokestop, TrsQuest) \
            .join(TrsQuest, and_(TrsQuest.GUID == Pokestop.pokestop_id,
                                 TrsQuest.layer == quest_layer.value), isouter=True)
        where_conditions = []

        lat, lon = geofence_helper.get_middle_from_fence()
        relevant_timezone: datetime.tzinfo = get_timezone_at(Location(lat, lon))
        tm_now = datetime.now(tz=relevant_timezone)
        timezone_midnight = tm_now.replace(hour=0, minute=0, second=0, microsecond=0)
        where_conditions.append(or_(TrsQuest.quest_timestamp < timezone_midnight.timestamp(),
                                    TrsQuest.GUID == None))

        min_lat, min_lon, max_lat, max_lon = geofence_helper.get_polygon_from_fence()
        where_conditions.append(and_(Pokestop.latitude >= min_lat,
                                     Pokestop.longitude >= min_lon,
                                     Pokestop.latitude <= max_lat,
                                     Pokestop.longitude <= max_lon))

        stmt = stmt.where(and_(*where_conditions))
        result = await session.execute(stmt)
        stops_without_quests: Dict[int, Pokestop] = {}
        for (stop, quest) in result.all():
            if quest and (quest.layer != quest_layer.value or quest.quest_timestamp > timezone_midnight.timestamp()):
                continue
            if geofence_helper.is_coord_inside_include_geofence(Location(float(stop.latitude), float(stop.longitude))):
                stops_without_quests[stop.pokestop_id] = stop
        return stops_without_quests

    @staticmethod
    async def get_in_rectangle(session: AsyncSession,
                               ne_corner: Optional[Location], sw_corner: Optional[Location],
                               old_ne_corner: Optional[Location] = None, old_sw_corner: Optional[Location] = None,
                               timestamp: Optional[int] = None) -> List[Pokestop]:
        stmt = select(Pokestop)
        where_conditions = [and_(Pokestop.latitude >= sw_corner.lat,
                                 Pokestop.longitude >= sw_corner.lng,
                                 Pokestop.latitude <= ne_corner.lat,
                                 Pokestop.longitude <= ne_corner.lng)]
        # TODO: Verify this works for all timezones...
        if (old_ne_corner and old_sw_corner
                and old_ne_corner.lat and old_ne_corner.lng and old_sw_corner.lat and old_sw_corner.lng):
            where_conditions.append(and_(Pokestop.latitude >= old_sw_corner.lat,
                                         Pokestop.longitude >= old_sw_corner.lng,
                                         Pokestop.latitude <= old_ne_corner.lat,
                                         Pokestop.longitude <= old_ne_corner.lng))
        if timestamp:
            where_conditions.append(Pokestop.last_updated >= DatetimeWrapper.fromtimestamp(timestamp))
        stmt = stmt.where(and_(*where_conditions))
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_stop_quest(session: AsyncSession) -> List[Tuple[str, int]]:
        """
        DbStatsReader::get_stop_quest
        returns list of tuples containing [date label or NO QUEST, count of stops]
        Args:
            session:

        Returns:

        """
        min_quest_timestamp = func.FROM_UNIXTIME(func.MIN(TrsQuest.quest_timestamp), '%y-%m-%d')
        # LEFT JOIN to fetch stops without quests
        stmt = select(
            func.IF(min_quest_timestamp == None, "No quest",
                    min_quest_timestamp),
            func.COUNT(Pokestop.pokestop_id)
        ).select_from(Pokestop) \
            .join(TrsQuest, TrsQuest.GUID == Pokestop.pokestop_id, isouter=True) \
            .group_by(func.FROM_UNIXTIME(TrsQuest.quest_timestamp, '%y-%m-%d'))
        result = await session.execute(stmt)
        results: List[Tuple[str, int]] = []
        for timestamp_as_str, count in result.all():
            results.append((timestamp_as_str, count))
        return results

    @staticmethod
    async def submit_pokestop_visited(session: AsyncSession, location: Location) -> None:
        stmt = update(Pokestop).where(and_(Pokestop.latitude == location.lat,
                                           Pokestop.longitude == location.lng)).values(Pokestop.vi)
        await session.execute(stmt)

    @staticmethod
    async def get_changed_since_or_incident(session: AsyncSession, _timestamp: int) -> List[Pokestop]:
        stmt = select(Pokestop) \
            .where(and_(Pokestop.last_updated > DatetimeWrapper.fromtimestamp(_timestamp),
                        or_(Pokestop.incident_start != None,
                            Pokestop.lure_expiration > DatetimeWrapper.fromtimestamp(0))))
        # TODO: Validate lure_expiration comparison works rather than DATEDIFF
        result = await session.execute(stmt)
        return result.scalars().all()
