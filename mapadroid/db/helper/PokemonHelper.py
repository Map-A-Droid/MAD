import datetime
import time
from functools import reduce
from typing import Optional, Tuple, Dict, List

from sqlalchemy import and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import Pokemon
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.utils.collections import Location
from mapadroid.utils.logging import get_logger, LoggerEnums

logger = get_logger(LoggerEnums.database)


# noinspection PyComparisonWithNone
class PokemonHelper:
    @staticmethod
    async def get(session: AsyncSession, encounter_id: int) -> Optional[Pokemon]:
        stmt = select(Pokemon).where(Pokemon.encounter_id == encounter_id)
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_encountered(session: AsyncSession, geofence_helper: GeofenceHelper, latest: int = 0) \
            -> Tuple[int, Dict[int, int]]:
        if geofence_helper is None:
            return 0, {}
        if latest == 0:
            # limiting the time frame to the last couple of minutes
            latest = time.time() - 15 * 60
        min_lat, min_lon, max_lat, max_lon = geofence_helper.get_polygon_from_fence()
        # TODO: Likely having some DB foo...
        stmt = select(Pokemon).where(and_(Pokemon.cp != None,
                                          Pokemon.disappear_time > datetime.datetime.utcnow() - datetime.timedelta(
                                              hours=1),
                                          Pokemon.last_modified > datetime.datetime.fromtimestamp(latest),
                                          Pokemon.latitude >= min_lat,
                                          Pokemon.longitude >= min_lon,
                                          Pokemon.latitude <= max_lat,
                                          Pokemon.longitude <= max_lon))
        result = await session.execute(stmt)
        encounter_id_infos: Dict[int, int] = {}
        for pokemon in result:
            if not geofence_helper.is_coord_inside_include_geofence([pokemon.latitude, pokemon.longitude]):
                continue
            latest = max(latest, pokemon.last_modified.timestamp())
            # TODO: Why was the original code adding an hour?
            #   "UNIX_TIMESTAMP(CONVERT_TZ(disappear_time + INTERVAL 1 HOUR, '+00:00', @@global.time_zone)), "
            encounter_id_infos[pokemon.encounter_id] = pokemon.disappear_time.timestamp()
        return latest, encounter_id_infos

    @staticmethod
    async def get_pokemon_spawn_counts(session: AsyncSession, hours: int = None) -> Dict:
        stmt = select(Pokemon.pokemon_id, func.COUNT(Pokemon.pokemon_id)).select_from(Pokemon)
        if hours:
            stmt = stmt.where(Pokemon.disappear_time > datetime.datetime.utcnow() - datetime.timedelta(hours=hours))
        stmt = stmt.group_by(Pokemon.pokemon_id)
        result = await session.execute(stmt)
        results: List = result.all()
        total = reduce(lambda x, y: x + y[1], results, 0)
        return {'pokemon': results, 'total': total}

    @staticmethod
    async def get_to_be_encountered(session: AsyncSession, geofence_helper: Optional[GeofenceHelper],
                                    min_time_left_seconds: int, eligible_mon_ids: Optional[List[int]]) -> List:
        if min_time_left_seconds is None or eligible_mon_ids is None:
            logger.warning(
                "DbWrapper::get_to_be_encountered: Not returning any encounters since no time left or "
                "eligible mon IDs specified. Make sure both settings are set in area options: "
                "min_time_left_seconds and mon_ids_iv ")
            return []
        logger.debug3("Getting mons to be encountered")
        stmt = select(Pokemon).where(and_(Pokemon.individual_attack == None,
                                          Pokemon.individual_defense == None,
                                          Pokemon.individual_stamina == None,
                                          Pokemon.encounter_id != 0,
                                          Pokemon.disappear_time.between(datetime.datetime.utcnow()
                                                                         + datetime.timedelta(
                                                                            seconds=min_time_left_seconds),
                                                                         datetime.datetime.utcnow()
                                                                         + datetime.timedelta(minutes=60)))
                                     .order_by(Pokemon.disappear_time))
        result = await session.execute(stmt)

        next_to_encounter = []
        for pokemon in result:
            if pokemon.pokemon_id not in eligible_mon_ids:
                continue
            elif pokemon.latitude is None or pokemon.longitude is None:
                logger.warning("lat or lng is none")
                continue
            elif geofence_helper and not geofence_helper.is_coord_inside_include_geofence(
                    [pokemon.latitude, pokemon.longitude]):
                logger.debug3("Excluded encounter at {}, {} since the coordinate is not inside the given include "
                              " fences", pokemon.latitude, pokemon.longitude)
                continue

            next_to_encounter.append((pokemon.pokemon_id, Location(pokemon.latitude, pokemon.longitude),
                                      pokemon.encounter_id))
        # now filter by the order of eligible_mon_ids
        to_be_encountered = []
        i = 0
        for mon_prio in eligible_mon_ids:
            for mon in next_to_encounter:
                if mon_prio == mon[0]:
                    to_be_encountered.append((i, mon[1], mon[2]))
            i += 1
        return to_be_encountered

    @staticmethod
    async def get_mons_in_rectangle(session: AsyncSession,
                                    ne_corner: Optional[Location] = None, sw_corner: Optional[Location] = None,
                                    old_ne_corner: Optional[Location] = None, old_sw_corner: Optional[Location] = None,
                                    timestamp: Optional[int] = None) -> List[Pokemon]:
        stmt = select(Pokemon)
        where_conditions = []
        where_conditions.append(Pokemon.disappear_time > datetime.datetime.utcnow())
        if ne_corner and sw_corner:
            where_conditions.append(and_(Pokemon.latitude >= sw_corner.lat,
                                         Pokemon.longitude >= sw_corner.lng,
                                         Pokemon.latitude <= ne_corner.lat,
                                         Pokemon.longitude <= ne_corner.lng))
        if old_ne_corner and old_sw_corner:
            where_conditions.append(and_(Pokemon.latitude >= old_sw_corner.lat,
                                         Pokemon.longitude >= old_sw_corner.lng,
                                         Pokemon.latitude <= old_ne_corner.lat,
                                         Pokemon.longitude <= old_ne_corner.lng))
        if timestamp:
            where_conditions.append(Pokemon.last_modified >= datetime.datetime.utcfromtimestamp(timestamp))

        stmt = stmt.where(and_(*where_conditions))
        result = await session.execute(stmt)
        return result.scalars().all()
