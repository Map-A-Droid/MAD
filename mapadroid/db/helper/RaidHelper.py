import time
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.db.model import Gym, Raid
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.utils.collections import Location


class RaidHelper:
    @staticmethod
    async def get(session: AsyncSession, gym_id: str) -> Optional[Raid]:
        stmt = select(Raid).where(Raid.gym_id == gym_id)
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_next_hatches(session: AsyncSession,
                               geofence_helper: GeofenceHelper = None) -> List[Tuple[int, Location]]:
        db_time_to_check = datetime.utcfromtimestamp(time.time())
        stmt = select(Raid.start, Gym.latitude, Gym.longitude) \
            .select_from(Raid).join(Gym, Gym.gym_id == Raid.gym_id) \
            .where(and_(Raid.end > db_time_to_check, Raid.pokemon_id != None))
        result = await session.execute(stmt)
        next_hatches: List[Tuple[int, Location]] = []
        for (start, latitude, longitude) in result.scalars():
            if latitude is None or longitude is None:
                # logger.warning("lat or lng is none")
                continue
            elif geofence_helper and not geofence_helper.is_coord_inside_include_geofence([latitude, longitude]):
                # logger.debug3("Excluded hatch at {}, {} since the coordinate is not inside the given include fences",
                #              latitude, longitude)
                continue
            next_hatches.append((int(start.timestamp()), Location(latitude, longitude)))

        # logger.debug4("Latest Q: {}", data)
        return next_hatches
