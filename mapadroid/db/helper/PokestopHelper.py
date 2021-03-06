from typing import Optional, List, Dict

from sqlalchemy import and_, join
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from mapadroid.db.model import Pokestop, TrsVisited
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.utils.collections import Location
from mapadroid.utils.logging import LoggerEnums, get_logger

logger = get_logger(LoggerEnums.database)


# noinspection PyComparisonWithNone
class PokestopHelper:
    @staticmethod
    async def get(session: AsyncSession, pokestop_id: str) -> Optional[Pokestop]:
        stmt = select(Pokestop).where(Pokestop.pokestop_id == pokestop_id)
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_at_location(session: AsyncSession, latitude: float, longitude: float) -> Optional[Pokestop]:
        stmt = select(Pokestop).where(and_(Pokestop.latitude == latitude,
                                           Pokestop.longitude == longitude))
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_locations_in_fence(session: AsyncSession, geofence_helper: GeofenceHelper,
                                     fence=None) -> List[Location]:
        min_lat, min_lon, max_lat, max_lon = geofence_helper.get_polygon_from_fence()
        if fence is not None:
            # TODO: probably gotta fix ST_Contains, ST_GeomFromText and Point...
            stmt = select(Pokestop).where(and_(Pokestop.latitude >= min_lat,
                                               Pokestop.longitude >= min_lon,
                                               Pokestop.latitude <= max_lat,
                                               Pokestop.longitude <= max_lon,
                                               func.ST_Contains(func.ST_GeomFromText(str(fence)),
                                                                func.POINT(Pokestop.latitude, Pokestop.longitude))))
        else:
            stmt = select(Pokestop).where(and_(Pokestop.latitude >= min_lat,
                                          Pokestop.longitude >= min_lon,
                                          Pokestop.latitude <= max_lat,
                                          Pokestop.longitude <= max_lon))
        result = await session.execute(stmt)
        list_of_coords: List[Location] = []
        for pokestop in result:
            list_of_coords.append(Location(pokestop.latitude, pokestop.longitude))
        return geofence_helper.get_geofenced_coordinates(list_of_coords)

    @staticmethod
    async def any_stops_unvisited(session: AsyncSession, geofence_helper: GeofenceHelper, origin: str) -> bool:
        return len(await PokestopHelper.stops_not_visited(session, geofence_helper, origin)) > 0

    @staticmethod
    async def stops_not_visited(session: AsyncSession, geofence_helper: GeofenceHelper, origin: str) -> List[Pokestop]:
        logger.debug3("DbWrapper::any_stops_unvisited called")
        min_lat, min_lon, max_lat, max_lon = geofence_helper.get_polygon_from_fence()
        stmt = select(Pokestop)\
            .join(TrsVisited, and_(Pokestop.pokestop_id == TrsVisited.pokestop_id,
                                   TrsVisited.origin == origin), isouter=True)\
            .where(and_(Pokestop.latitude >= min_lat, Pokestop.longitude >= min_lon,
                        Pokestop.latitude <= max_lat, Pokestop.longitude <= max_lon,
                        TrsVisited.origin == None))
        result = await session.execute(stmt)
        unvisited: List[Pokestop] = []
        for pokestop in result:
            if geofence_helper.is_coord_inside_include_geofence([pokestop.latitude, pokestop.longitude]):
                unvisited.append(pokestop)
        return unvisited

    @staticmethod
    async def update_location(session: AsyncSession, fort_id: str, latitude: float, longitude: float) -> None:
        pokestop: Optional[Pokestop] = await PokestopHelper.get(session, fort_id)
        if not pokestop:
            return
        pokestop.latitude = latitude
        pokestop.longitude = longitude
        session.add(pokestop)

    @staticmethod
    async def delete(session: AsyncSession, latitude: float, longitude: float) -> None:
        pokestop: Optional[Pokestop] = await PokestopHelper.get_at_location(session, latitude, longitude)
        if pokestop:
            session.delete(pokestop)

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
        for pokestop in result:
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
                .select_from(Pokestop)\
                .join(TrsVisited, and_(Pokestop.pokestop_id == TrsVisited.pokestop_id,
                                       TrsVisited.origin == origin), isouter=True) \
                .where(where_condition).order_by("distance")
            if limit > 0:
                stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            for stop, _distance in result:
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

