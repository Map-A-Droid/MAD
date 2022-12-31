import json
import math
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Tuple

import sqlalchemy
from aioredis import Redis
from bitstring import BitArray
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.db.PooledQueryExecutor import PooledQueryExecutor
from mapadroid.db.helper.GymDetailHelper import GymDetailHelper
from mapadroid.db.helper.GymHelper import GymHelper
from mapadroid.db.helper.PokemonDisplayHelper import PokemonDisplayHelper
from mapadroid.db.helper.PokemonHelper import PokemonHelper
from mapadroid.db.helper.PokestopHelper import PokestopHelper
from mapadroid.db.helper.RaidHelper import RaidHelper
from mapadroid.db.helper.TrsEventHelper import TrsEventHelper
from mapadroid.db.helper.TrsQuestHelper import TrsQuestHelper
from mapadroid.db.helper.TrsS2CellHelper import TrsS2CellHelper
from mapadroid.db.helper.TrsSpawnHelper import TrsSpawnHelper
from mapadroid.db.helper.TrsStatsDetectSeenTypeHelper import TrsStatsDetectSeenTypeHelper
from mapadroid.db.helper.WeatherHelper import WeatherHelper
from mapadroid.db.model import (Gym, GymDetail, Pokemon, Pokestop, Raid,
                                TrsEvent, TrsQuest, TrsSpawn,
                                Weather, TrsStatsDetectSeenType)
from mapadroid.utils.DatetimeWrapper import DatetimeWrapper
from mapadroid.utils.gamemechanicutil import (gen_despawn_timestamp,
                                              is_mon_ditto)
from mapadroid.utils.logging import get_logger, LoggerEnums
from mapadroid.utils.madConstants import (REDIS_CACHETIME_MON_LURE_IV, REDIS_CACHETIME_STOP_DETAILS,
                                          REDIS_CACHETIME_GYMS,
                                          REDIS_CACHETIME_RAIDS, REDIS_CACHETIME_CELLS,
                                          REDIS_CACHETIME_WEATHER, REDIS_CACHETIME_POKESTOP_DATA)
from mapadroid.utils.madGlobals import MonSeenTypes, QuestLayer
from mapadroid.utils.questGen import QuestGen
from mapadroid.utils.s2Helper import S2Helper

logger = get_logger(LoggerEnums.database)


class DbPogoProtoSubmit:
    """
    Hosts all methods related to submitting protocol data to the database.
    TODO: Most of the code is actually unrelated to database stuff and should be
     moved outside the db package.
    """
    default_spawndef = 240

    def __init__(self, db_exec: PooledQueryExecutor, args):
        self._db_exec: PooledQueryExecutor = db_exec
        self._args = args
        self._cache: Redis = None

    async def setup(self):
        self._cache: Redis = await self._db_exec.get_cache()

    async def mons(self, session: AsyncSession, timestamp: float,
                   map_proto: dict) -> List[int]:
        """
        Update/Insert mons from a map_proto dict

        Returns: List of encounterIDs of wild mons in GMO
        """
        logger.debug3("DbPogoProtoSubmit::mons called with data received")
        cells = map_proto.get("cells", None)
        encounter_ids_in_gmo = []
        now = DatetimeWrapper.fromtimestamp(timestamp)
        if not cells:
            return encounter_ids_in_gmo
        for cell in cells:
            for wild_mon in cell["wild_pokemon"]:
                spawnid = int(str(wild_mon["spawnpoint_id"]), 16)
                lat = wild_mon["latitude"]
                lon = wild_mon["longitude"]
                mon_id = wild_mon["pokemon_data"]["id"]
                encounter_id = wild_mon["encounter_id"]

                if encounter_id < 0:
                    encounter_id = encounter_id + 2 ** 64
                encounter_ids_in_gmo.append(encounter_id)

                cache_key = "mon{}-{}".format(encounter_id, mon_id)
                if await self._cache.exists(cache_key):
                    continue

                # get known spawn end time and feed into despawn time calculation
                # getdetspawntime = self._get_detected_endtime(str(spawnid))
                spawnpoint: Optional[TrsSpawn] = await TrsSpawnHelper.get(session, spawnid)
                despawn_time_unix = gen_despawn_timestamp(spawnpoint.calc_endminsec if spawnpoint else None, timestamp,
                                                          self._args.default_unknown_timeleft)
                despawn_time = DatetimeWrapper.fromtimestamp(despawn_time_unix)

                if spawnpoint is None:
                    logger.debug3("adding mon (#{}) at {}, {}. Despawns at {} (init) ({})", mon_id, lat, lon,
                                  despawn_time.strftime("%Y-%m-%d %H:%M:%S"), spawnid)
                else:
                    logger.debug3("adding mon (#{}) at {}, {}. Despawns at {} (non-init) ({})", mon_id, lat, lon,
                                  despawn_time.strftime("%Y-%m-%d %H:%M:%S"), spawnid)

                async with session.begin_nested() as nested_transaction:
                    mon: Optional[Pokemon] = await PokemonHelper.get(session, encounter_id)
                    if not mon:
                        mon: Pokemon = Pokemon()
                        mon.encounter_id = encounter_id
                        mon.spawnpoint_id = spawnid
                        mon.latitude = lat
                        mon.longitude = lon
                    mon.pokemon_id = mon_id
                    if mon.seen_type not in [MonSeenTypes.encounter.name, MonSeenTypes.lure_encounter.name]:
                        # TODO: Any other types not to overwrite?
                        mon.seen_type = MonSeenTypes.wild.name
                    if mon_id == 132:
                        # handle ditto
                        mon.pokemon_id = 132
                        mon.gender = 3
                        mon.costume = 0
                        mon.form = 0
                    else:
                        mon.pokemon_id = mon_id
                        mon.gender = wild_mon["pokemon_data"]["display"]["gender_value"]
                        mon.costume = wild_mon["pokemon_data"]["display"]["costume_value"]
                        mon.form = wild_mon["pokemon_data"]["display"]["form_value"]

                    # TODO handle weather boost condition changes for redoing IV+ditto (set ivs to null again)
                    #  Further we should probably reset IVs if pokemon_id changes as well

                    mon.disappear_time = despawn_time
                    mon.weather_boosted_condition = wild_mon["pokemon_data"]["display"]["weather_boosted_value"]
                    mon.last_modified = now
                    try:
                        session.add(mon)
                        await nested_transaction.commit()
                        cache_time = int(despawn_time_unix - int(DatetimeWrapper.now().timestamp()))
                        if cache_time > 0:
                            await self._cache.set(cache_key, 1, ex=cache_time)
                    except sqlalchemy.exc.IntegrityError as e:
                        logger.debug("Failed committing mon {} ({}). Safe to ignore.", encounter_id, str(e))
                        await nested_transaction.rollback()
                        continue
                await session.commit()
        return encounter_ids_in_gmo

    async def mons_nearby(self, session: AsyncSession, timestamp: float,
                          map_proto: dict) -> Tuple[List[int], List[int]]:
        """
        Insert nearby mons
        """
        stop_encounters: List[int] = []
        cell_encounters: List[int] = []
        logger.debug3("DbPogoProtoSubmit::nearby_mons called with data received")
        cells = map_proto.get("cells", [])
        if not cells:
            return cell_encounters, stop_encounters

        for cell in cells:
            cell_id = cell.get("id")
            nearby_mons = cell.get("nearby_pokemon", [])
            for nearby_mon in nearby_mons:
                display = nearby_mon["display"]
                weather_boosted = display["weather_boosted_value"]
                mon_id = nearby_mon["id"]
                encounter_id = nearby_mon["encounter_id"]
                if encounter_id < 0:
                    encounter_id = encounter_id + 2 ** 64

                cache_key = "monnear{}-{}".format(encounter_id, mon_id)
                encounter_key = "moniv{}-{}-{}".format(encounter_id, weather_boosted, mon_id)
                wild_key = "mon{}-{}".format(encounter_id, mon_id)
                if (await self._cache.exists(wild_key) or await self._cache.exists(encounter_key)
                        or await self._cache.exists(cache_key)):
                    continue
                stop_id = nearby_mon["fort_id"]
                form = display["form_value"]
                costume = display["costume_value"]
                gender = display["gender_value"]

                now = DatetimeWrapper.fromtimestamp(timestamp)
                disappear_time = now + timedelta(minutes=self._args.default_nearby_timeleft)

                if not self._args.disable_nearby_cell and not stop_id and cell_id:
                    lat, lon, _ = S2Helper.get_position_from_cell(cell_id)
                    stop_id = None
                    db_cell = cell_id
                    seen_type: MonSeenTypes = MonSeenTypes.nearby_cell
                    # TODO: Move above cache check...
                    cell_encounters.append(encounter_id)
                else:
                    db_cell = None
                    seen_type: MonSeenTypes = MonSeenTypes.nearby_stop
                    fort: Optional[Union[Pokestop, Gym]] = await PokestopHelper.get(session, stop_id)
                    if not fort:
                        fort: Optional[Gym] = await GymHelper.get(session, stop_id)

                    if fort:
                        lat, lon = fort.latitude, fort.longitude
                    else:
                        lat, lon = (0, 0)
                    # TODO: Move above cache check...
                    stop_encounters.append(encounter_id)

                spawnpoint = 0
                async with session.begin_nested() as nested_transaction:
                    mon: Optional[Pokemon] = await PokemonHelper.get(session, encounter_id)
                    if not mon:
                        mon: Pokemon = Pokemon()
                        mon.encounter_id = encounter_id
                        mon.spawnpoint_id = spawnpoint
                        mon.latitude = lat
                        mon.longitude = lon
                        mon.cell_id = db_cell
                        mon.fort_id = stop_id
                        mon.seen_type = seen_type.name
                        mon.disappear_time = disappear_time

                    if mon_id == 132:
                        # handle ditto
                        mon.pokemon_id = 132
                        mon.gender = 3
                        mon.costume = 0
                        mon.form = 0
                    else:
                        mon.pokemon_id = mon_id
                        mon.gender = gender
                        mon.costume = costume
                        mon.form = form
                    mon.weather_boosted_condition = weather_boosted
                    mon.last_modified = now
                    try:
                        session.add(mon)
                        await nested_transaction.commit()
                        await self._cache.set(cache_key, 1, ex=self._args.default_nearby_timeleft * 60)
                    except sqlalchemy.exc.IntegrityError as e:
                        logger.debug("Failed committing nearby mon {} ({}). Safe to ignore.", encounter_id, str(e))
                        await nested_transaction.rollback()

        return cell_encounters, stop_encounters

    async def mon_iv(self, session: AsyncSession, timestamp: float,
                     encounter_proto: dict) -> Optional[Tuple[int, bool]]:
        """
        Update/Insert a mon with IVs
        """
        wild_pokemon = encounter_proto.get("wild_pokemon", None)
        if wild_pokemon is None or wild_pokemon.get("encounter_id", 0) == 0 or not str(wild_pokemon["spawnpoint_id"]):
            logger.warning("Encounter proto of no use (status: {}).", encounter_proto.get('status', None))
            return None

        encounter_id = wild_pokemon["encounter_id"]
        pokemon_data = wild_pokemon.get("pokemon_data")
        mon_id = pokemon_data.get("id")
        pokemon_display = pokemon_data.get("display", {})
        weather_boosted = pokemon_display.get('weather_boosted_value', None)
        if encounter_id < 0:
            encounter_id = encounter_id + 2 ** 64
        cache_key = "moniv{}-{}-{}".format(encounter_id, weather_boosted, mon_id)
        if await self._cache.exists(cache_key):
            return None

        logger.debug3("Updating IV sent for encounter at {}", timestamp)

        spawnid = int(str(wild_pokemon["spawnpoint_id"]), 16)
        spawnpoint: Optional[TrsSpawn] = await TrsSpawnHelper.get(session, spawnid)
        despawn_time_unix = gen_despawn_timestamp(spawnpoint.calc_endminsec if spawnpoint else None, timestamp,
                                                  self._args.default_unknown_timeleft)
        despawn_time = DatetimeWrapper.fromtimestamp(despawn_time_unix)

        latitude = wild_pokemon.get("latitude")
        longitude = wild_pokemon.get("longitude")
        shiny = wild_pokemon["pokemon_data"]["display"].get("is_shiny", 0)
        is_shiny: bool = True if shiny == 1 else False
        if spawnpoint is None:
            logger.debug3("updating IV mon #{} at {}, {}. Despawning at {} (init)", pokemon_data["id"], latitude,
                          longitude, despawn_time)
        else:
            logger.debug3("updating IV mon #{} at {}, {}. Despawning at {} (non-init)", pokemon_data["id"],
                          latitude, longitude, despawn_time)

        capture_probability = encounter_proto.get("capture_probability")
        capture_probability_list = capture_probability.get("capture_probability_list")
        if capture_probability_list is not None:
            capture_probability_list = capture_probability_list.replace("[", "").replace("]", "").split(",")

        # ditto detector
        form, gender, mon_id, move_1, move_2 = await self._extract_data_or_set_ditto(mon_id, pokemon_data,
                                                                                     pokemon_display)
        now = DatetimeWrapper.fromtimestamp(timestamp)
        time_start_submit = time.time()
        mon: Optional[Pokemon] = await PokemonHelper.get(session, encounter_id)
        if not mon:
            mon: Pokemon = Pokemon()
            mon.encounter_id = encounter_id
        mon.spawnpoint_id = spawnid
        mon.pokemon_id = mon_id
        mon.latitude = latitude
        mon.longitude = longitude
        mon.cell_id = None
        mon.seen_type = MonSeenTypes.encounter.name
        mon.disappear_time = despawn_time
        mon.individual_attack = pokemon_data.get("individual_attack")
        mon.individual_defense = pokemon_data.get("individual_defense")
        mon.individual_stamina = pokemon_data.get("individual_stamina")
        mon.move_1 = move_1
        mon.move_2 = move_2
        mon.cp = pokemon_data.get("cp")
        mon.cp_multiplier = pokemon_data.get("cp_multiplier")
        mon.weight = pokemon_data.get("weight")
        mon.height = pokemon_data.get("height")
        mon.gender = gender
        mon.catch_prob_1 = float(capture_probability_list[0])
        mon.catch_prob_2 = float(capture_probability_list[1])
        mon.catch_prob_3 = float(capture_probability_list[2])
        mon.rating_attack = mon.rating_defense = None
        mon.weather_boosted_condition = weather_boosted
        mon.costume = pokemon_display.get("costume_value", None)
        mon.form = form
        mon.last_modified = now
        logger.debug("Submitting IV {} scanned at {}", encounter_id, timestamp)
        session.add(mon)
        await self.maybe_save_ditto(session, pokemon_display, encounter_id, mon_id, pokemon_data)
        await session.commit()
        cache_time = int(despawn_time_unix - int(DatetimeWrapper.now().timestamp()))
        if cache_time > 0:
            await self._cache.set(cache_key, 1, ex=cache_time)
        time_done = time.time() - time_start_submit
        logger.debug("Done updating mon IV in DB in {} seconds", time_done)

        return encounter_id, is_shiny

    async def _extract_data_or_set_ditto(self, mon_id, pokemon_data, pokemon_display):
        if is_mon_ditto(pokemon_data):
            # mon must be a ditto :D
            mon_id = 132
            gender = 3
            move_1 = 242
            move_2 = 133
            form = 0
        else:
            gender = pokemon_display.get("gender_value", None)
            move_1 = pokemon_data.get("move_1")
            move_2 = pokemon_data.get("move_2")
            form = pokemon_display.get("form_value", None)
        return form, gender, mon_id, move_1, move_2

    async def mon_lure_iv(self, session: AsyncSession, timestamp: float,
                          encounter_proto: dict) -> Optional[Tuple[int, datetime]]:
        """
        Update/Insert a lure mon with IVs
        """
        logger.debug3("Updating IV sent for encounter at {}", timestamp)

        pokemon_data = encounter_proto.get("pokemon", {})
        mon_id = pokemon_data.get("id")
        display = pokemon_data.get("display", {})
        weather_boosted = display.get('weather_boosted_value')
        encounter_id = display.get("display_id", 0)

        if encounter_id < 0:
            encounter_id = encounter_id + 2 ** 64

        cache_key = "moniv{}-{}-{}".format(encounter_id, weather_boosted, mon_id)
        if await self._cache.exists(cache_key):
            return None

        # ditto detector
        form, gender, mon_id, move_1, move_2 = await self._extract_data_or_set_ditto(mon_id, pokemon_data,
                                                                                     display)

        capture_probability = encounter_proto.get("capture_probability", {})
        capture_probability_list = capture_probability.get("capture_probability_list", None)
        if capture_probability_list is not None:
            capture_probability_list = capture_probability_list.replace("[", "").replace("]", "").split(",")

        now = DatetimeWrapper.fromtimestamp(timestamp)
        time_start_submit = time.time()
        async with session.begin_nested() as nested_transaction:
            mon: Optional[Pokemon] = await PokemonHelper.get(session, encounter_id)
            if not mon:
                mon: Pokemon = Pokemon()
                mon.encounter_id = encounter_id
                mon.latitude = 0
                mon.longitude = 0
                mon.spawnpoint_id = 0
                # TODO: Does this make sense? 2 Minute despawn to at least show it?
                mon.disappear_time = now + timedelta(minutes=2)
                mon.rating_attack = mon.rating_defense = None
            mon.pokemon_id = mon_id
            mon.costume = display.get("costume_value", None)
            mon.form = form
            mon.gender = gender
            mon.seen_type = MonSeenTypes.lure_encounter.name
            mon.individual_attack = pokemon_data.get("individual_attack")
            mon.individual_defense = pokemon_data.get("individual_defense")
            mon.individual_stamina = pokemon_data.get("individual_stamina")
            mon.move_1 = move_1
            mon.move_2 = move_2
            mon.cp = pokemon_data.get("cp")
            mon.cp_multiplier = pokemon_data.get("cp_multiplier")
            mon.weight = pokemon_data.get("weight")
            mon.height = pokemon_data.get("height")
            if capture_probability_list:
                mon.catch_prob_1 = float(capture_probability_list[0])
                mon.catch_prob_2 = float(capture_probability_list[1])
                mon.catch_prob_3 = float(capture_probability_list[2])
            mon.weather_boosted_condition = weather_boosted
            mon.last_modified = now

            logger.debug("Submitting IV {}", encounter_id)
            session.add(mon)
            await self.maybe_save_ditto(session, display, encounter_id, mon_id, pokemon_data)
            await nested_transaction.commit()
            await self._cache.set(cache_key, 1, ex=REDIS_CACHETIME_MON_LURE_IV)
            time_done = time.time() - time_start_submit
            logger.debug("Done updating mon lure IV in DB in {} seconds", time_done)
        return encounter_id, now

    async def mon_lure_noiv(self, session: AsyncSession, timestamp: float, gmo: dict) -> List[int]:
        """
        Update/Insert Lure mons from a map_proto dict
        """
        logger.debug3("DbPogoProtoSubmit::mon_lure_noiv called with data received")
        cells = gmo.get("cells", None)
        encounter_ids: List[int] = []
        if cells is None:
            return encounter_ids

        for cell in cells:
            for fort in cell["forts"]:
                lure_mon = fort.get("active_pokemon", {})
                mon_id = lure_mon.get("id", 0)
                if fort["type"] == 1 and mon_id > 0:
                    encounter_id = lure_mon["encounter_id"]

                    if encounter_id < 0:
                        encounter_id = encounter_id + 2 ** 64
                    encounter_ids.append(encounter_id)
                    cache_key = "monlurenoiv{}".format(encounter_id)
                    if await self._cache.exists(cache_key):
                        continue

                    lat = fort["latitude"]
                    lon = fort["longitude"]
                    stopid = fort["id"]
                    disappear_time = DatetimeWrapper.fromtimestamp(
                        lure_mon["expiration_timestamp"] / 1000)

                    now = DatetimeWrapper.fromtimestamp(timestamp)

                    display = lure_mon["display"]
                    form = display["form_value"]
                    costume = display["costume_value"]
                    gender = display["gender_value"]
                    weather_boosted = display["weather_boosted_value"]

                    async with session.begin_nested() as nested_transaction:
                        mon: Optional[Pokemon] = await PokemonHelper.get(session, encounter_id)
                        if not mon:
                            mon: Pokemon = Pokemon()
                            mon.encounter_id = encounter_id
                            mon.spawnpoint_id = 0
                            mon.seen_type = MonSeenTypes.lure_wild.name
                            mon.pokemon_id = mon_id
                            mon.gender = gender
                            mon.weather_boosted_condition = weather_boosted
                            mon.costume = costume
                            mon.form = form
                        mon.latitude = lat
                        mon.longitude = lon
                        mon.disappear_time = disappear_time
                        mon.fort_id = stopid
                        mon.last_modified = now
                        try:
                            logger.debug("Submitting lured non-IV mon {}", encounter_id)
                            session.add(mon)
                            await nested_transaction.commit()
                            await self._cache.set(cache_key, 1, ex=REDIS_CACHETIME_MON_LURE_IV)
                        except sqlalchemy.exc.IntegrityError as e:
                            logger.debug("Failed committing lured non-IV mon {} ({}). Safe to ignore.", encounter_id,
                                         str(e))
                            await nested_transaction.rollback()
        return encounter_ids

    async def update_seen_type_stats(self, session: AsyncSession, **kwargs):
        insert: Dict[int, Dict[MonSeenTypes, datetime]] = {}
        for seen_type in [MonSeenTypes.encounter, MonSeenTypes.wild, MonSeenTypes.nearby_stop,
                          MonSeenTypes.nearby_cell, MonSeenTypes.lure_encounter, MonSeenTypes.lure_wild]:
            encounters = kwargs.get(seen_type.name, None)
            if encounters is None:
                continue

            for encounter_id, seen_time in encounters:
                if encounter_id not in insert:
                    insert[encounter_id] = {}
                insert[encounter_id][seen_type] = seen_time

        for encounter_id, values in insert.items():
            encounter: Optional[datetime] = values.get(MonSeenTypes.encounter, None)
            wild: Optional[datetime] = values.get(MonSeenTypes.wild, None)
            nearby_stop: Optional[datetime] = values.get(MonSeenTypes.nearby_stop, None)
            nearby_cell: Optional[datetime] = values.get(MonSeenTypes.nearby_cell, None)
            lure_encounter: Optional[datetime] = values.get(MonSeenTypes.lure_encounter, None)
            lure_wild: Optional[datetime] = values.get(MonSeenTypes.lure_wild, None)
            async with session.begin_nested() as nested_transaction:
                stat_seen_type: Optional[TrsStatsDetectSeenType] = await TrsStatsDetectSeenTypeHelper.get(session,
                                                                                                          encounter_id)
                if not stat_seen_type:
                    stat_seen_type: TrsStatsDetectSeenType = TrsStatsDetectSeenType()
                    stat_seen_type.encounter_id = encounter_id
                if encounter:
                    stat_seen_type.encounter = encounter
                if wild:
                    stat_seen_type.wild = wild
                if nearby_stop:
                    stat_seen_type.nearby_stop = nearby_stop
                if nearby_cell:
                    stat_seen_type.nearby_cell = nearby_cell
                if lure_encounter:
                    stat_seen_type.lure_encounter = lure_encounter
                if lure_wild:
                    stat_seen_type.lure_wild = lure_wild
                logger.debug("Submitting mon seen stat {}", encounter_id)
                session.add(stat_seen_type)
                try:
                    await nested_transaction.commit()
                except sqlalchemy.exc.IntegrityError as e:
                    await nested_transaction.rollback()
                    logger.debug("Failed submitting stat...")

    async def spawnpoints(self, session: AsyncSession, map_proto: dict, received_timestamp: int):
        logger.debug3("DbPogoProtoSubmit::spawnpoints called with data received")
        cells = map_proto.get("cells", None)
        if cells is None:
            return False
        spawn_ids: List[int] = []
        for cell in cells:
            for wild_mon in cell["wild_pokemon"]:
                spawn_ids.append(int(str(wild_mon['spawnpoint_id']), 16))

        spawndef: Dict[int, TrsSpawn] = await self._get_spawndef(session, spawn_ids)
        current_event: Optional[TrsEvent] = await TrsEventHelper.get_current_event(session, True)
        spawns_do_add: List[TrsSpawn] = []
        received_time: datetime = DatetimeWrapper.fromtimestamp(received_timestamp)
        for cell in cells:
            for wild_mon in cell["wild_pokemon"]:
                spawnid = int(str(wild_mon["spawnpoint_id"]), 16)
                lat, lng, _ = S2Helper.get_position_from_cell(
                    int(str(wild_mon["spawnpoint_id"]) + "00000", 16))
                despawntime = wild_mon["time_till_hidden"]

                minpos = self._get_current_spawndef_pos()
                # TODO: retrieve the spawndefs by a single executemany and pass that...
                spawn = spawndef.get(spawnid, None)
                if spawn:
                    newspawndef = self._set_spawn_see_minutesgroup(spawn.spawndef, minpos)
                else:
                    newspawndef = self._set_spawn_see_minutesgroup(self.default_spawndef, minpos)

                # TODO: This may break another known timer...
                if 0 <= int(despawntime) <= 90000:
                    fulldate = received_time + timedelta(milliseconds=despawntime)
                    earliest_unseen = int(despawntime)
                    calcendtime = fulldate.strftime("%M:%S")

                    # TODO: First try to fetch a TrsSpawn, then handle the above...
                    # TODO: We can just use the above dict of spawns....
                    if spawn:
                        # Update...
                        # TODO: Is it that simple?
                        spawn.earliest_unseen = min(spawn.earliest_unseen, earliest_unseen)
                        if current_event.id == spawn.eventid or current_event.id != 1 and spawn.eventid != 1:
                            spawn.spawndef = newspawndef
                    else:
                        spawn: TrsSpawn = TrsSpawn()
                        spawn.spawnpoint = spawnid
                        spawn.latitude = lat
                        spawn.longitude = lng
                        spawn.earliest_unseen = earliest_unseen
                        spawn.spawndef = newspawndef
                        spawn.eventid = current_event.id if current_event else 1
                        spawn.first_detection = DatetimeWrapper.fromtimestamp(received_timestamp)
                    spawn.last_scanned = DatetimeWrapper.fromtimestamp(received_timestamp)
                    spawn.calc_endminsec = calcendtime
                else:
                    # TODO: Reduce "complexity..."
                    if spawn:
                        if current_event.id == spawn.eventid or current_event.id != 1 and spawn.eventid != 1:
                            spawn.spawndef = newspawndef
                    else:
                        spawn: TrsSpawn = TrsSpawn()
                        spawn.spawnpoint = spawnid
                        spawn.latitude = lat
                        spawn.longitude = lng
                        spawn.earliest_unseen = 99999999
                        spawn.spawndef = newspawndef
                        spawn.eventid = current_event.id if current_event else 1
                    spawn.last_non_scanned = DatetimeWrapper.now()
                spawns_do_add.append(spawn)
        session.add_all(spawns_do_add)

    async def stops(self, session: AsyncSession, map_proto: dict):
        """
        Update/Insert pokestops from a map_proto dict
        """
        logger.debug3("DbPogoProtoSubmit::stops called with data received")
        cells = map_proto.get("cells", None)
        if cells is None:
            return False

        for cell in cells:
            for fort in cell["forts"]:
                if fort["type"] == 1:
                    await self._handle_pokestop_data(session, fort)
        return True

    async def stop_details(self, session: AsyncSession, stop_proto: dict):
        """
        Update/Insert pokestop details from a GMO
        :param stop_proto:
        :return:

        Args:
            session:
            session:
        """
        logger.debug3("DbPogoProtoSubmit::pokestops_details called")

        stop: Optional[Pokestop] = await self._extract_args_single_stop_details(session, stop_proto)
        if stop:
            alt_modified_time = int(math.ceil(DatetimeWrapper.now().timestamp() / 1000)) * 1000
            cache_key = "stopdetail{}{}".format(stop.pokestop_id,
                                                stop_proto.get("last_modified_timestamp_ms", alt_modified_time))
            if await self._cache.exists(cache_key):
                return True
            async with session.begin_nested() as nested_transaction:
                try:
                    session.add(stop)
                    await nested_transaction.commit()
                    await self._cache.set(cache_key, 1, ex=REDIS_CACHETIME_STOP_DETAILS)
                except sqlalchemy.exc.IntegrityError as e:
                    logger.warning("Failed committing stop details of {} ({})", stop.pokestop_id, str(e))
                    await nested_transaction.rollback()
        return stop is not None

    async def quest(self, session: AsyncSession, quest_proto: dict, quest_gen: QuestGen,
                    quest_layer: QuestLayer) -> bool:
        """

        Args:
            quest_layer: the quest layer being scanned
            session:
            quest_proto:
            quest_gen:

        Returns: True if quest was submitted to DB

        """
        logger.debug3("DbPogoProtoSubmit::quest called")
        fort_id = quest_proto.get("fort_id", None)
        if fort_id is None:
            return False
        if "challenge_quest" not in quest_proto:
            return False
        protoquest = quest_proto["challenge_quest"]["quest"]
        rewards = protoquest.get("quest_rewards", None)
        if not rewards:
            return False
        protoquest_display = quest_proto["challenge_quest"]["quest_display"]
        quest_title_resource_id = protoquest_display.get("title", None)
        reward = rewards[0]
        item = reward['item']
        encounter = reward['pokemon_encounter']
        goal = protoquest['goal']

        quest_type = protoquest.get("quest_type", None)
        quest_template = protoquest.get("template_id", None)

        reward_type = reward.get("type", None)
        item_item = item.get("item", None)
        item_amount = item.get("amount", None)
        pokemon_id = encounter.get("pokemon_id", None)
        stardust = reward.get("stardust", None)

        if reward_type == 4:
            item_amount = reward.get('candy', {}).get('amount', 0)
            pokemon_id = reward.get('candy', {}).get('pokemon_id', 0)
        elif reward_type == 12:
            item_amount = reward.get('mega_resource', {}).get('amount', 0)
            pokemon_id = reward.get('mega_resource', {}).get('pokemon_id', 0)
        elif reward_type == 1:
            #item_amount = reward.get('exp', 0)
            stardust = reward.get('exp', 0)

        form_id = encounter.get("pokemon_display", {}).get("form_value", 0)
        costume_id = encounter.get("pokemon_display", {}).get("costume_value", 0)
        target = goal.get("target", None)
        condition = goal.get("condition", None)

        json_condition = json.dumps(condition)
        task = await quest_gen.questtask(int(quest_type), json_condition, int(target), str(quest_template),
                                         quest_title_resource_id)
        quest: Optional[TrsQuest] = await TrsQuestHelper.get(session, fort_id, quest_layer)
        if not quest:
            quest = TrsQuest()
            quest.GUID = fort_id
            quest.layer = quest_layer.value
        quest.quest_type = quest_type
        quest.quest_timestamp = int(time.time())
        quest.quest_stardust = stardust
        quest.quest_pokemon_id = pokemon_id
        quest.quest_pokemon_form_id = form_id
        quest.quest_pokemon_costume_id = costume_id
        quest.quest_reward_type = reward_type
        quest.quest_item_id = item_item
        quest.quest_item_amount = item_amount
        quest.quest_target = target
        quest.quest_condition = json_condition
        quest.quest_reward = json.dumps(rewards)
        quest.quest_task = task
        quest.quest_template = quest_template
        quest.quest_title = quest_title_resource_id

        logger.debug3("DbPogoProtoSubmit::quest submitted quest type {} at stop {}", quest_type, fort_id)
        async with session.begin_nested() as nested_transaction:
            try:
                session.add(quest)
                await nested_transaction.commit()
            except sqlalchemy.exc.IntegrityError as e:
                logger.warning("Failed committing quest of stop {}, ({})", fort_id, str(e))
                await nested_transaction.rollback()
        return True

    async def gyms(self, session: AsyncSession, map_proto: dict, received_timestamp: int):
        """
        Update/Insert gyms from a map_proto dict
        """
        logger.debug3("DbPogoProtoSubmit::gyms called with data received from")
        cells = map_proto.get("cells", None)
        if cells is None:
            return False
        time_receiver: datetime = DatetimeWrapper.fromtimestamp(received_timestamp)
        for cell in cells:
            for gym in cell["forts"]:
                if gym["type"] == 0:
                    gymid = gym["id"]
                    last_modified_ts = gym["last_modified_timestamp_ms"] / 1000
                    last_modified = DatetimeWrapper.fromtimestamp(
                        last_modified_ts)
                    latitude = gym["latitude"]
                    longitude = gym["longitude"]
                    s2_cell_id = S2Helper.lat_lng_to_cell_id(latitude, longitude)
                    weather: Optional[Weather] = await WeatherHelper.get(session, str(s2_cell_id))
                    gameplay_weather: int = weather.gameplay_weather if weather is not None else 0
                    cache_key = "gym{}{}{}".format(gymid, last_modified_ts, gameplay_weather)
                    if await self._cache.exists(cache_key):
                        continue
                    guard_pokemon_id = gym["gym_details"]["guard_pokemon"]
                    team_id = gym["gym_details"]["owned_by_team"]
                    slots_available = gym["gym_details"]["slots_available"]
                    is_ex_raid_eligible = gym["gym_details"]["is_ex_raid_eligible"]
                    is_ar_scan_eligible = gym["is_ar_scan_eligible"]
                    is_in_battle = gym['gym_details']['is_in_battle']
                    is_enabled = gym.get('enabled', 1)

                    gym_obj: Optional[Gym] = await GymHelper.get(session, gymid)
                    if not gym_obj:
                        gym_obj: Gym = Gym()
                        gym_obj.gym_id = gymid
                    gym_obj.team_id = team_id
                    gym_obj.guard_pokemon_id = guard_pokemon_id
                    gym_obj.slots_available = slots_available
                    gym_obj.enabled = is_enabled
                    gym_obj.latitude = latitude
                    gym_obj.longitude = longitude
                    gym_obj.total_cp = gym.get("gym_display", {}).get("total_gym_cp", 0)
                    gym_obj.is_in_battle = is_in_battle
                    gym_obj.last_modified = last_modified
                    gym_obj.last_scanned = time_receiver
                    gym_obj.is_ex_raid_eligible = is_ex_raid_eligible
                    gym_obj.is_ar_scan_eligible = is_ar_scan_eligible
                    gym_obj.weather_boosted_condition = gameplay_weather

                    gym_detail: Optional[GymDetail] = await GymDetailHelper.get(session, gymid)
                    if not gym_detail:
                        gym_detail: GymDetail = GymDetail()
                        gym_detail.gym_id = gymid
                        gym_detail.name = "unknown"
                        gym_detail.url = ""
                    gym_url = gym.get("image_url", "")
                    if gym_url and gym_url.strip():
                        gym_detail.url = gym_url.strip()
                    gym_detail.last_scanned = time_receiver
                    async with session.begin_nested() as nested_transaction:
                        try:
                            session.add(gym_obj)
                            session.add(gym_detail)
                            await nested_transaction.commit()
                            await self._cache.set(cache_key, 1, ex=REDIS_CACHETIME_GYMS)
                        except sqlalchemy.exc.IntegrityError as e:
                            logger.warning("Failed committing gym data of {} ({})", gymid, str(e))
                            await nested_transaction.rollback()
        return True

    async def gym(self, session: AsyncSession, map_proto: dict):
        """
        Update gyms from a map_proto dict
        """
        logger.debug3("Updating gyms")
        if map_proto.get("result", 0) != 1:
            return False
        status = map_proto.get("gym_status_and_defenders", None)
        if status is None:
            return False
        fort_proto = status.get("pokemon_fort_proto", None)
        if fort_proto is None:
            return False
        gym_id = fort_proto["id"]
        name = map_proto["name"]
        description = map_proto["description"]
        url = map_proto["url"]

        gym_detail: Optional[GymDetail] = await GymDetailHelper.get(session, gym_id)
        if not gym_detail:
            return False
        touched: bool = False
        if name is not None and name != "":
            touched = True
            gym_detail.name = name
        if description is not None and description != "":
            touched = True
            gym_detail.description = description
        if url is not None and url != "":
            touched = True
            gym_detail.url = url
        if touched:
            async with session.begin_nested() as nested_transaction:
                try:
                    session.add(gym_detail)
                    await nested_transaction.commit()
                except sqlalchemy.exc.IntegrityError as e:
                    logger.warning("Failed committing gym info {} ({})", gym_id, str(e))
                    await nested_transaction.rollback()
        return True

    async def raids(self, session: AsyncSession, map_proto: dict, timestamp: int) -> int:
        """
        Update/Insert raids from a map_proto dict

        Returns: amount of raids in GMO processed
        """
        logger.debug3("DbPogoProtoSubmit::raids called with data received")
        cells = map_proto.get("cells", None)
        if cells is None:
            return False
        raids_seen: int = 0
        received_at: datetime = DatetimeWrapper.fromtimestamp(timestamp)
        for cell in cells:
            for gym in cell["forts"]:
                if gym["type"] == 0 and gym["gym_details"]["has_raid"]:
                    gym_has_raid = gym["gym_details"]["raid_info"]["has_pokemon"]
                    if gym_has_raid:
                        raids_seen += 1
                        raid_info = gym["gym_details"]["raid_info"]

                        pokemon_id = raid_info["raid_pokemon"]["id"]
                        cp = raid_info["raid_pokemon"]["cp"]
                        move_1 = raid_info["raid_pokemon"]["move_1"]
                        move_2 = raid_info["raid_pokemon"]["move_2"]
                        form = raid_info["raid_pokemon"]["display"]["form_value"]
                        gender = raid_info["raid_pokemon"]["display"]["gender_value"]
                        costume = raid_info["raid_pokemon"]["display"]["costume_value"]
                        evolution = raid_info["raid_pokemon"]["display"].get("current_temp_evolution", 0)
                    else:
                        pokemon_id = None
                        cp = 0
                        move_1 = 1
                        move_2 = 2
                        form = None
                        gender = None
                        costume = None
                        evolution = 0

                    raid_end_sec = int(gym["gym_details"]["raid_info"]["raid_end"] / 1000)
                    raid_spawn_sec = int(gym["gym_details"]["raid_info"]["raid_spawn"] / 1000)
                    raid_battle_sec = int(gym["gym_details"]["raid_info"]["raid_battle"] / 1000)

                    raidend_date = DatetimeWrapper.fromtimestamp(
                        float(raid_end_sec))
                    raidspawn_date = DatetimeWrapper.fromtimestamp(float(raid_spawn_sec))
                    raidstart_date = DatetimeWrapper.fromtimestamp(float(raid_battle_sec))

                    is_exclusive = gym["gym_details"]["raid_info"]["is_exclusive"]
                    level = gym["gym_details"]["raid_info"]["level"]
                    gymid = gym["id"]

                    logger.debug3("Adding/Updating gym {} with level {} ending at {}", gymid, level,
                                  raidend_date.strftime("%Y-%m-%d %H:%M:%S"))

                    cache_key = "raid{}{}{}".format(gymid, pokemon_id, raid_end_sec)
                    if await self._cache.exists(cache_key):
                        continue

                    raid: Optional[Raid] = await RaidHelper.get(session, gymid)
                    if not raid:
                        raid: Raid = Raid()
                        raid.gym_id = gymid
                    elif raid.last_scanned > received_at:
                        continue
                    raid.level = level
                    raid.spawn = raidspawn_date
                    raid.start = raidstart_date
                    raid.end = raidend_date
                    raid.pokemon_id = pokemon_id
                    raid.cp = cp
                    raid.move_1 = move_1
                    raid.move_2 = move_2
                    raid.last_scanned = received_at
                    raid.form = form
                    raid.is_exclusive = is_exclusive
                    raid.gender = gender
                    raid.costume = costume
                    raid.evolution = evolution
                    async with session.begin_nested() as nested_transaction:
                        try:
                            session.add(raid)
                            await nested_transaction.commit()
                            await self._cache.set(cache_key, 1, ex=REDIS_CACHETIME_RAIDS)
                        except sqlalchemy.exc.IntegrityError as e:
                            logger.warning("Failed committing raid for gym {} ({})", gymid, str(e))
                            await nested_transaction.rollback()
        logger.debug3("DbPogoProtoSubmit::raids: Done submitting raids with data received")
        return raids_seen

    async def weather(self, session: AsyncSession, map_proto, received_timestamp) -> bool:
        """
        Update/Insert weather from a map_proto dict
        """
        logger.debug3("DbPogoProtoSubmit::weather called with data received")
        cells = map_proto.get("cells", None)
        if cells is None:
            return False

        for client_weather in map_proto["client_weather"]:
            time_of_day = map_proto.get("time_of_day_value", 0)
            await self._handle_weather_data(session, client_weather, time_of_day, received_timestamp)
        return True

    async def cells(self, session: AsyncSession, map_proto: dict):
        protocells = map_proto.get("cells", [])

        for cell in protocells:
            cell_id = cell["id"]

            if cell_id < 0:
                cell_id = cell_id + 2 ** 64
            cache_key = "s2cell{}".format(cell_id)
            if await self._cache.exists(cache_key):
                continue
            await self._cache.set(cache_key, 1, ex=REDIS_CACHETIME_CELLS)
            logger.debug3("Updating s2cell {}", cell_id)
            try:
                await TrsS2CellHelper.insert_update_cell(session, cell)
            except sqlalchemy.exc.IntegrityError as e:
                logger.debug("Failed committing cell {} ({})", cell_id, str(e))
                await self._cache.set(cache_key, 1, ex=1)

    async def _handle_pokestop_data(self, session: AsyncSession,
                                    stop_data: Dict) -> Optional[Pokestop]:
        if stop_data["type"] != 1:
            logger.info("{} is not a pokestop", stop_data)
            return
        alt_modified_time = int(math.ceil(DatetimeWrapper.now().timestamp() / 1000)) * 1000
        cache_key = "stop{}{}".format(stop_data["id"], stop_data.get("last_modified_timestamp_ms", alt_modified_time))
        if await self._cache.exists(cache_key):
            return

        now = DatetimeWrapper.fromtimestamp(time.time())
        last_modified = DatetimeWrapper.fromtimestamp(
            stop_data["last_modified_timestamp_ms"] / 1000
        )
        lure = DatetimeWrapper.fromtimestamp(0)
        active_fort_modifier = None
        incident_start = None
        incident_expiration = None
        incident_grunt_type = None
        is_ar_scan_eligible = stop_data["is_ar_scan_eligible"]

        if len(stop_data["active_fort_modifier"]) > 0:
            # get current lure duration
            trs_event: Optional[TrsEvent] = await TrsEventHelper.get_current_event(session)
            if trs_event and trs_event.event_lure_duration:
                lure_duration = int(trs_event.event_lure_duration)
            else:
                lure_duration = int(30)

            active_fort_modifier = stop_data["active_fort_modifier"][0]
            lure = DatetimeWrapper.fromtimestamp(
                lure_duration * 60 + (stop_data["last_modified_timestamp_ms"] / 1000)
            )

        if "pokestop_displays" in stop_data \
                and len(stop_data["pokestop_displays"]) > 0 \
                and stop_data["pokestop_displays"][0]["character_display"] is not None \
                and stop_data["pokestop_displays"][0]["character_display"]["character"] > 1:
            start_ms = stop_data["pokestop_displays"][0]["incident_start_ms"]
            expiration_ms = stop_data["pokestop_displays"][0]["incident_expiration_ms"]
            incident_grunt_type = stop_data["pokestop_displays"][0]["character_display"]["character"]

            if start_ms > 0:
                incident_start = DatetimeWrapper.fromtimestamp(start_ms / 1000)

            if expiration_ms > 0:
                incident_expiration = DatetimeWrapper.fromtimestamp(expiration_ms / 1000)
        elif "pokestop_display" in stop_data:
            start_ms = stop_data["pokestop_display"]["incident_start_ms"]
            expiration_ms = stop_data["pokestop_display"]["incident_expiration_ms"]
            incident_grunt_type = stop_data["pokestop_display"]["character_display"]["character"]

            if start_ms > 0:
                incident_start = DatetimeWrapper.fromtimestamp(start_ms / 1000)

            if expiration_ms > 0:
                incident_expiration = DatetimeWrapper.fromtimestamp(expiration_ms / 1000)
        stop_id = stop_data["id"]

        pokestop: Optional[Pokestop] = await PokestopHelper.get(session, stop_id)
        if not pokestop:
            pokestop: Pokestop = Pokestop()
            pokestop.pokestop_id = stop_id
        pokestop.enabled = stop_data.get("enabled", 1)
        pokestop.latitude = stop_data["latitude"]
        pokestop.longitude = stop_data["longitude"]
        pokestop.last_modified = last_modified
        pokestop.lure_expiration = lure
        pokestop.last_updated = now
        pokestop.active_fort_modifier = active_fort_modifier
        pokestop.incident_start = incident_start
        pokestop.incident_expiration = incident_expiration
        pokestop.incident_grunt_type = incident_grunt_type
        pokestop.is_ar_scan_eligible = is_ar_scan_eligible
        try:
            session.add(pokestop)
            await session.commit()
            await self._cache.set(cache_key, 1, ex=REDIS_CACHETIME_POKESTOP_DATA)
        except sqlalchemy.exc.IntegrityError as e:
            logger.warning("Failed committing stop {} ({})", stop_id, str(e))
            await session.rollback()

    async def _extract_args_single_stop_details(self, session: AsyncSession, stop_data) -> Optional[Pokestop]:
        if stop_data.get("type", 999) != 1:
            return None
        image = stop_data.get("image_urls", None)
        name = stop_data.get("name", None)
        now = DatetimeWrapper.now()
        stop_id = stop_data["fort_id"]
        pokestop: Optional[Pokestop] = await PokestopHelper.get(session, stop_id)
        if not pokestop:
            pokestop: Pokestop = Pokestop()
            pokestop.pokestop_id = stop_data["id"]
        elif pokestop.last_updated > now:
            return None
        pokestop.latitude = stop_data["latitude"]
        pokestop.longitude = stop_data["longitude"]
        pokestop.name = name
        if image and image[0]:
            pokestop.image = image[0]
        pokestop.last_updated = now
        pokestop.enabled = stop_data.get("enabled", 1)
        pokestop.last_modified = DatetimeWrapper.fromtimestamp(
            stop_data.get("last_modified_timestamp_ms", 0) / 1000)
        return pokestop

    async def _handle_weather_data(self, session: AsyncSession, client_weather_data, time_of_day,
                                   received_timestamp) -> None:
        cell_id = client_weather_data["cell_id"]
        real_lat, real_lng = S2Helper.middle_of_cell(cell_id)

        display_weather_data = client_weather_data.get("display_weather", None)
        if display_weather_data is None:
            return
        else:
            gameplay_weather = client_weather_data["gameplay_weather"]["gameplay_condition"]
        cache_key = "weather{}{}{}{}{}{}{}".format(cell_id, display_weather_data.get("rain_level", 0),
                                                   display_weather_data.get("wind_level", 0),
                                                   display_weather_data.get("snow_level", 0),
                                                   display_weather_data.get("fog_level", 0),
                                                   display_weather_data.get("wind_direction", 0),
                                                   gameplay_weather)
        if await self._cache.exists(cache_key):
            return
        date_received = DatetimeWrapper.fromtimestamp(received_timestamp)
        async with session.begin_nested() as nested_transaction:
            try:
                weather: Optional[Weather] = await WeatherHelper.get(session, str(cell_id))
                if not weather:
                    weather: Weather = Weather()
                    weather.s2_cell_id = str(cell_id)
                    weather.latitude = real_lat
                    weather.longitude = real_lng
                weather.cloud_level = display_weather_data.get("cloud_level", 0)
                weather.rain_level = display_weather_data.get("rain_level", 0)
                weather.wind_level = display_weather_data.get("wind_level", 0)
                weather.snow_level = display_weather_data.get("snow_level", 0)
                weather.fog_level = display_weather_data.get("fog_level", 0)
                weather.wind_direction = display_weather_data.get("wind_direction", 0)
                weather.gameplay_weather = gameplay_weather
                # TODO: Properly extract severity and warn..
                weather.warn_weather = 0
                weather.severity = 0
                weather.world_time = time_of_day
                weather.last_updated = date_received

                if not weather:
                    return

                session.add(weather)
                await self._cache.set(cache_key, 1, ex=REDIS_CACHETIME_WEATHER)
                await nested_transaction.commit()
            except sqlalchemy.exc.IntegrityError as e:
                logger.warning("Failed committing weather of cell {} ({})", cell_id, str(e))
                await nested_transaction.rollback()

    async def _get_spawndef(self, session: AsyncSession, spawn_ids: List[int]) -> Dict[int, TrsSpawn]:
        if not spawn_ids:
            return {}
        logger.debug3("DbPogoProtoSubmit::_get_spawndef called")

        spawnret = {}
        res: List[TrsSpawn] = await TrsSpawnHelper.get_all(session, spawn_ids)
        for spawn in res:
            spawnret[int(spawn.spawnpoint)] = spawn
        return spawnret

    def _get_current_spawndef_pos(self):
        minute_value = int(DatetimeWrapper.now().strftime("%M"))
        if minute_value < 15:
            pos = 4
        elif minute_value < 30:
            pos = 5
        elif minute_value < 45:
            pos = 6
        elif minute_value < 60:
            pos = 7
        else:
            pos = None
        return pos

    def _set_spawn_see_minutesgroup(self, spawndef, pos):
        minte_group = BitArray(uint=spawndef, length=8)
        if pos == 4:
            minte_group[0] = 0
            minte_group[4] = 1
        if pos == 5:
            minte_group[1] = 0
            minte_group[5] = 1
        if pos == 6:
            minte_group[2] = 0
            minte_group[6] = 1
        if pos == 7:
            minte_group[3] = 0
            minte_group[7] = 1
        return minte_group.uint

    def get_time_ms(self):
        return int(time.time() * 1000)

    async def maybe_save_ditto(self, session: AsyncSession, display: Dict, encounter_id: int, mon_id: int,
                               pokemon_data: Dict):
        if mon_id == 132:
            # Save ditto disguise
            await PokemonDisplayHelper.insert_ignore(session, encounter_id,
                                                     pokemon_id=pokemon_data.get('id'),
                                                     form=display.get("form_value", None),
                                                     gender=display.get("gender_value", None),
                                                     costume=display.get("costume_value", None))
