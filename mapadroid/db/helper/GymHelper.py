from typing import Optional, List

from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import Gym
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.utils.collections import Location


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
        for gym in result:
            list_of_coords.append(Location(gym.latitude, gym.longitude))
        return geofence_helper.get_geofenced_coordinates(list_of_coords)

