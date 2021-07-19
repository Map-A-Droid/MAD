from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, case, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import Gym, GymDetail, Raid
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.utils.collections import Location
from mapadroid.utils.madGlobals import TeamColours


class GymHelper:
    @staticmethod
    async def get(session: AsyncSession, gym_id: str) -> Optional[Gym]:
        stmt = select(Gym).where(Gym.gym_id == gym_id)
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_locations_in_fence(session: AsyncSession, geofence_helper: GeofenceHelper) -> List[Location]:
        min_lat, min_lon, max_lat, max_lon = geofence_helper.get_polygon_from_fence()
        stmt = select(Gym).where(and_(Gym.latitude >= min_lat,
                                      Gym.longitude >= min_lon,
                                      Gym.latitude <= max_lat,
                                      Gym.longitude <= max_lon))
        result = await session.execute(stmt)

        list_of_coords: List[Location] = []
        for gym in result.scalars():
            list_of_coords.append(Location(float(gym.latitude), float(gym.longitude)))
        return geofence_helper.get_geofenced_coordinates(list_of_coords)

    @staticmethod
    async def get_gyms_in_rectangle(session: AsyncSession,
                                    ne_corner: Optional[Location] = None, sw_corner: Optional[Location] = None,
                                    old_ne_corner: Optional[Location] = None, old_sw_corner: Optional[Location] = None,
                                    timestamp: Optional[int] = None) -> Dict[int, Tuple[Gym, GymDetail, Raid]]:
        stmt = select(Gym, GymDetail, Raid) \
            .join(GymDetail, GymDetail.gym_id == Gym.gym_id, isouter=False) \
            .join(Raid, Raid.gym_id == Gym.gym_id, isouter=True)
        where_conditions = []
        if (ne_corner and sw_corner
                and ne_corner.lat and ne_corner.lng and sw_corner.lat and sw_corner.lng):
            where_conditions.append(and_(Gym.latitude >= sw_corner.lat,
                                         Gym.longitude >= sw_corner.lng,
                                         Gym.latitude <= ne_corner.lat,
                                         Gym.longitude <= ne_corner.lng))
        if (old_ne_corner and old_sw_corner
                and old_ne_corner.lat and old_ne_corner.lng and old_sw_corner.lat and old_sw_corner.lng):
            where_conditions.append(and_(Gym.latitude >= old_sw_corner.lat,
                                         Gym.longitude >= old_sw_corner.lng,
                                         Gym.latitude <= old_ne_corner.lat,
                                         Gym.longitude <= old_ne_corner.lng))
        if timestamp:
            where_conditions.append(Gym.last_scanned >= datetime.fromtimestamp(timestamp))

        stmt = stmt.where(and_(*where_conditions))
        result = await session.execute(stmt)
        gyms: Dict[int, Tuple[Gym, GymDetail, Raid]] = {}
        for (gym, gym_detail, raid) in result.all():
            gyms[gym.gym_id] = (gym, gym_detail, raid)
        return gyms

    @staticmethod
    async def get_gym_count(session: AsyncSession) -> Dict[str, int]:
        """
        DbStatsReader::get_gym_count
        Args:
            session:

        Returns: Dict[team_as_str, count]

        """
        stmt = select(
            case((Gym.team_id == 0, TeamColours.WHITE.value),
                 (Gym.team_id == 1, TeamColours.BLUE.value),
                 (Gym.team_id == 2, TeamColours.RED.value),
                 else_=TeamColours.YELLOW.value),
            func.count(Gym.team_id)) \
            .select_from(Gym) \
            .group_by(Gym.team_id)
        result = await session.execute(stmt)
        team_count: Dict[str, int] = {}
        for team, count in result.all():
            team_count[team] = count
        return team_count

    @staticmethod
    async def get_changed_since(session: AsyncSession, timestamp: int) -> List[Tuple[Gym, GymDetail]]:
        stmt = select(Gym, GymDetail) \
            .join(GymDetail, GymDetail.gym_id == Gym.gym_id, isouter=False) \
            .where(Gym.last_modified >= datetime.fromtimestamp(timestamp))
        # TODO: Consider last_scanned above
        result = await session.execute(stmt)
        return result.all()
