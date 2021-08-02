import datetime
import time
from typing import List, Optional, Tuple

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.db.model import Gym, Raid, GymDetail
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.utils.DatetimeWrapper import DatetimeWrapper
from mapadroid.utils.collections import Location


class RaidHelper:
    @staticmethod
    async def get(session: AsyncSession, gym_id: str) -> Optional[Raid]:
        stmt = select(Raid).where(Raid.gym_id == gym_id)
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_next_hatches(session: AsyncSession,
                               geofence_helper: GeofenceHelper = None,
                               only_next_n_seconds: Optional[int] = None) -> List[Tuple[int, Location]]:
        db_time_to_check = DatetimeWrapper.now()
        stmt = select(Raid.start, Gym.latitude, Gym.longitude) \
            .select_from(Raid).join(Gym, Gym.gym_id == Raid.gym_id)
        where_conditions = [and_(Raid.end > db_time_to_check, Raid.pokemon_id != None)]

        if only_next_n_seconds:
            where_conditions.append(Raid.start < db_time_to_check + datetime.timedelta(seconds=only_next_n_seconds))
        stmt = stmt.where(and_(*where_conditions))
        result = await session.execute(stmt)
        next_hatches: List[Tuple[int, Location]] = []
        for (start, latitude, longitude) in result.all():
            if latitude is None or longitude is None:
                # logger.warning("lat or lng is none")
                continue
            elif geofence_helper and not geofence_helper.is_coord_inside_include_geofence([latitude, longitude]):
                # logger.debug3("Excluded hatch at {}, {} since the coordinate is not inside the given include fences",
                #              latitude, longitude)
                continue
            next_hatches.append((int(start.timestamp()), Location(float(latitude), float(longitude))))

        # logger.debug4("Latest Q: {}", data)
        return next_hatches

    @staticmethod
    async def get_raids_changed_since(session: AsyncSession, _timestamp: int,
                                      geofence_helper: GeofenceHelper = None) -> List[Tuple[Raid, GymDetail, Gym]]:
        stmt = select(Raid, GymDetail, Gym) \
            .select_from(Raid) \
            .join(GymDetail, GymDetail.gym_id == Raid.gym_id) \
            .join(Gym, Gym.gym_id == Raid.gym_id) \
            .where(Raid.last_scanned > DatetimeWrapper.fromtimestamp(_timestamp))
        result = await session.execute(stmt)
        changed_data: List[Tuple[Raid, GymDetail, Gym]] = []
        raw = result.all()
        for (raid, gym_detail, gym) in raw:
            if gym.latitude is None or gym.longitude is None:
                continue
            elif geofence_helper \
                    and not geofence_helper.is_coord_inside_include_geofence([gym.latitude, gym.longitude]):
                continue
            changed_data.append((raid, gym_detail, gym))
        return changed_data
