import datetime
import time
from functools import reduce
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy import and_, delete, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from mapadroid.db.model import (Pokemon, PokemonDisplay, Pokestop, TrsSpawn,
                                TrsStatsDetectWildMonRaw)
from mapadroid.geofence.geofenceHelper import GeofenceHelper
from mapadroid.utils.DatetimeWrapper import DatetimeWrapper
from mapadroid.utils.collections import Location
from mapadroid.utils.logging import LoggerEnums, get_logger
from mapadroid.utils.madGlobals import MonSeenTypes

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

        stmt = select(Pokemon).where(and_(Pokemon.disappear_time > DatetimeWrapper.now() - datetime.timedelta(
            hours=1),
                                          Pokemon.last_modified > DatetimeWrapper.fromtimestamp(latest),
                                          Pokemon.latitude >= min_lat,
                                          Pokemon.longitude >= min_lon,
                                          Pokemon.latitude <= max_lat,
                                          Pokemon.longitude <= max_lon,
                                          Pokemon.cp != None
                                          ))
        result = await session.execute(stmt)
        encounter_id_infos: Dict[int, int] = {}
        for pokemon in result.scalars().all():
            if not geofence_helper.is_coord_inside_include_geofence([pokemon.latitude, pokemon.longitude]):
                continue
            latest = max(latest, pokemon.last_modified.timestamp())
            # Add an hour to avoid encountering unknown disappear times again
            encounter_id_infos[pokemon.encounter_id] = int(pokemon.disappear_time.timestamp() + 60 * 60)
        return latest, encounter_id_infos

    @staticmethod
    async def get_pokemon_spawn_counts(session: AsyncSession, hours: int = None) -> Dict:
        stmt = select(Pokemon.pokemon_id, func.COUNT(Pokemon.pokemon_id)).select_from(Pokemon)
        if hours:
            stmt = stmt.where(Pokemon.disappear_time > DatetimeWrapper.now() - datetime.timedelta(hours=hours))
        # TODO: Adjust as group_by may not work - tho we have a count above. TEST IT
        stmt = stmt.group_by(Pokemon.pokemon_id)
        result = await session.execute(stmt)
        results: List = result.all()
        total = reduce(lambda x, y: x + y[1], results, 0)
        return {'pokemon': results, 'total': total}

    @staticmethod
    async def get_to_be_encountered(session: AsyncSession, geofence_helper: Optional[GeofenceHelper],
                                    min_time_left_seconds: int, eligible_mon_ids: Optional[List[int]]) -> List[Tuple[int, Location, int]]:
        if min_time_left_seconds is None or not eligible_mon_ids:
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
                                          Pokemon.seen_type != MonSeenTypes.nearby_cell.name,
                                          Pokemon.disappear_time.between(DatetimeWrapper.now()
                                                                         + datetime.timedelta(
                                              seconds=min_time_left_seconds),
                                                                         DatetimeWrapper.now()
                                                                         + datetime.timedelta(minutes=60)))
                                     ).order_by(Pokemon.disappear_time)
        result = await session.execute(stmt)

        next_to_encounter = []
        for pokemon in result.scalars().all():
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

            next_to_encounter.append((pokemon.pokemon_id, Location(float(pokemon.latitude), float(pokemon.longitude)),
                                      pokemon.encounter_id, pokemon.seen_type, pokemon.cell_id))
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
        where_conditions = [Pokemon.disappear_time > DatetimeWrapper.now()]
        if (ne_corner and sw_corner
                and ne_corner.lat and ne_corner.lng and sw_corner.lat and sw_corner.lng):
            where_conditions.append(and_(Pokemon.latitude >= sw_corner.lat,
                                         Pokemon.longitude >= sw_corner.lng,
                                         Pokemon.latitude <= ne_corner.lat,
                                         Pokemon.longitude <= ne_corner.lng))
        if (old_ne_corner and old_sw_corner
                and old_ne_corner.lat and old_ne_corner.lng and old_sw_corner.lat and old_sw_corner.lng):
            where_conditions.append(and_(Pokemon.latitude >= old_sw_corner.lat,
                                         Pokemon.longitude >= old_sw_corner.lng,
                                         Pokemon.latitude <= old_ne_corner.lat,
                                         Pokemon.longitude <= old_ne_corner.lng))
        if timestamp:
            where_conditions.append(Pokemon.last_modified >= DatetimeWrapper.fromtimestamp(timestamp))

        stmt = stmt.where(and_(*where_conditions))
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_all_shiny(session: AsyncSession, timestamp_after: Optional[int] = None,
                            timestamp_before: Optional[int] = None) -> Dict[int,
                                                                            Tuple[Pokemon,
                                                                                  List[TrsStatsDetectWildMonRaw]]]:
        """
        Used to be DbStatsReader::get_shiny_stats_v2
        Args:
            session:
            timestamp_after:
            timestamp_before:

        Returns: Dict of {encounterID : Tuple[Pokemon, List[TrsStatsDetectMonRaw]}

        """
        stmt = select(Pokemon, TrsStatsDetectWildMonRaw) \
            .join(TrsStatsDetectWildMonRaw, Pokemon.encounter_id == TrsStatsDetectWildMonRaw.encounter_id)
        where_conditions = [TrsStatsDetectWildMonRaw.is_shiny == 1]
        if timestamp_after:
            where_conditions.append(Pokemon.last_modified > DatetimeWrapper.fromtimestamp(timestamp_after))
        if timestamp_before:
            where_conditions.append(Pokemon.last_modified < DatetimeWrapper.fromtimestamp(timestamp_before))
        stmt = stmt.where(and_(*where_conditions))
        # SQLAlchemy does not handle group by very well it appears so we will do it in python...
        result = await session.execute(stmt)
        mapped: Dict[int, Tuple[Pokemon, List[TrsStatsDetectWildMonRaw]]] = {}
        for (mon, stats) in result.all():
            if mon.encounter_id not in mapped:
                mapped[mon.encounter_id] = (mon, [])
            mapped[mon.encounter_id][1].append(stats)

        return mapped

    @staticmethod
    async def get_count_iv_scanned_of_mon_ids(session: AsyncSession, mon_ids: Set[int],
                                              timestamp_after: Optional[int] = None,
                                              timestamp_before: Optional[int] = None) -> List[
        Tuple[int, int, int, int, int]]:
        """
        used to be DbStatsReader::get_shiny_stats_global_v2
        Args:
            session:
            mon_ids:
            timestamp_after:
            timestamp_before:

        Returns: List of tuples consisting of (count('*'), Pokemon.pokemon_id, Pokemon.form, Pokemon.gender, Pokemon.costume)
            of all mons that have been scanned for IV

        """
        stmt = select(func.count('*'), Pokemon.pokemon_id, Pokemon.form, Pokemon.gender, Pokemon.costume) \
            .select_from(Pokemon)
        where_conditions = [Pokemon.individual_attack != None,
                            Pokemon.pokemon_id.in_(mon_ids)]
        if timestamp_after:
            where_conditions.append(Pokemon.last_modified > DatetimeWrapper.fromtimestamp(timestamp_after))
        if timestamp_before:
            where_conditions.append(Pokemon.last_modified < DatetimeWrapper.fromtimestamp(timestamp_before))
        # Group_by works in this case as we use COUNT
        stmt = stmt.where(and_(*where_conditions)) \
            .group_by(Pokemon.pokemon_id, Pokemon.form)
        result = await session.execute(stmt)
        results = []
        for res in result.all():
            results.append(res)
        return results

    @staticmethod
    async def get_pokemon_count(session: AsyncSession,
                                include_last_n_minutes: Optional[int] = None) -> List[Tuple[int, int, int]]:
        """
        DbStatsReader::get_pokemon_count
        Args:
            session:
            include_last_n_minutes:

        Returns: List[Tuple[timestamp_of_full_hour, count_of_distinct_encounter_ids, iv_scanned_bool]]

        """
        iv = func.IF(Pokemon.cp == None, 0, 1).label("iv")
        timestamp = func.unix_timestamp(
            func.DATE_FORMAT(func.min(Pokemon.last_modified), '%y-%m-%d %k:00:00')) \
            .label("timestamp")
        stmt = select(
            timestamp,
            func.count(Pokemon.encounter_id.distinct()),
            iv) \
            .select_from(Pokemon)
        if include_last_n_minutes:
            minutes = DatetimeWrapper.now().replace(
                minute=0, second=0, microsecond=0) - datetime.timedelta(minutes=include_last_n_minutes)
            stmt = stmt.where(Pokemon.last_modified >= minutes)
        stmt = stmt.group_by(iv,
                             func.day(func.TIMESTAMP(Pokemon.last_modified)),
                             func.hour(func.TIMESTAMP(Pokemon.last_modified))) \
            .order_by(timestamp)
        result = await session.execute(stmt)
        results = []
        for res in result.all():
            results.append(res)
        return results

    @staticmethod
    async def get_best_pokemon_spawns(session: AsyncSession, limit: Optional[int] = None) -> List[Pokemon]:
        """
        DbStatsReader::get_best_pokemon_spawns
        Args:
            session:
            limit: Number of entries to return at most

        Returns: the last seen N "perfect" mons

        """
        stmt = select(Pokemon).where(and_(Pokemon.individual_attack == 15,
                                          Pokemon.individual_defense == 15,
                                          Pokemon.individual_stamina == 15)) \
            .order_by(desc(Pokemon.last_modified))
        if limit:
            stmt = stmt.limit(limit)
        result = await session.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_noniv_encounters_count(session: AsyncSession,
                                         last_n_minutes: Optional[int] = 240) -> List[Tuple[int, Location]]:
        """
        DbStatsReader::get_noniv_encounters_count
        Args:
            session:
            last_n_minutes:

        Returns: List of tuples of (the amount of mons not scanned for IV, in a location)

        """
        stmt = select(func.COUNT("*"),
                      Pokemon.latitude,
                      Pokemon.longitude)
        where_conditions = [Pokemon.cp != None]
        if last_n_minutes:
            time_to_check_after = DatetimeWrapper.now() - datetime.timedelta(minutes=last_n_minutes)
            where_conditions.append(Pokemon.last_modified > time_to_check_after)
        stmt = stmt.where(and_(*where_conditions)) \
            .group_by(Pokemon.latitude, Pokemon.longitude)
        result = await session.execute(stmt)
        results: List[Tuple[int, Location]] = []
        for count, lat, lng in result.all():
            results.append((count, Location(float(lat), float(lng))))
        return results

    @staticmethod
    async def get_changed_since(session: AsyncSession, _timestamp: int,
                                mon_types: Optional[Set[MonSeenTypes]] = None) -> List[Tuple[Pokemon, TrsSpawn,
                                                                                             Optional[Pokestop],
                                                                                             Optional[PokemonDisplay]]]:
        if not mon_types:
            mon_types = {MonSeenTypes.encounter, MonSeenTypes.lure_encounter}

        raw_types: List[str] = [x.name for x in mon_types]
        if {MonSeenTypes.nearby_stop, MonSeenTypes.lure_wild, MonSeenTypes.lure_encounter} & mon_types:
            # Lured/Nearby stops are to be included in the result set...
            stmt = select(Pokemon, TrsSpawn, Pokestop, PokemonDisplay) \
                .join(TrsSpawn, TrsSpawn.spawnpoint == Pokemon.spawnpoint_id, isouter=True)
            stmt = stmt.join(Pokestop, Pokestop.pokestop_id == Pokemon.fort_id, isouter=True)
        else:
            stmt = select(Pokemon, TrsSpawn, None, PokemonDisplay) \
                .join(TrsSpawn, TrsSpawn.spawnpoint == Pokemon.spawnpoint_id, isouter=True)
        stmt = stmt.join(PokemonDisplay, Pokemon.encounter_id == PokemonDisplay.encounter_id, isouter=True)
        stmt = stmt.where(and_(Pokemon.last_modified >= DatetimeWrapper.fromtimestamp(_timestamp),
                               Pokemon.seen_type.in_(raw_types)))

        result = await session.execute(stmt)
        return result.all()

    @staticmethod
    async def delete_older_than_n_hours(session: AsyncSession, hours: int, limit: Optional[int]) -> None:
        where_condition = Pokemon.disappear_time < DatetimeWrapper.now() - datetime.timedelta(hours=hours)
        stmt = delete(Pokemon).where(where_condition)
        if limit:
            encounter_ids_query = select(Pokemon.encounter_id).where(where_condition).limit(limit)
            result_encounter_ids = await session.execute(encounter_ids_query)
            encounter_ids = result_encounter_ids.scalars().all()
            stmt = delete(Pokemon).where(Pokemon.encounter_id.in_(encounter_ids))
        await session.execute(stmt)
