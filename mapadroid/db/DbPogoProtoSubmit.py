import asyncio
import json
import math
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union

import sqlalchemy
from aioredis import Redis
from bitstring import BitArray
from sqlalchemy.ext.asyncio import AsyncSession

from mapadroid.cache import NoopCache
from mapadroid.db.helper.GymDetailHelper import GymDetailHelper
from mapadroid.db.helper.GymHelper import GymHelper
from mapadroid.db.helper.PokemonHelper import PokemonHelper
from mapadroid.db.helper.PokestopHelper import PokestopHelper
from mapadroid.db.helper.RaidHelper import RaidHelper
from mapadroid.db.helper.TrsEventHelper import TrsEventHelper
from mapadroid.db.helper.TrsQuestHelper import TrsQuestHelper
from mapadroid.db.helper.TrsS2CellHelper import TrsS2CellHelper
from mapadroid.db.helper.TrsSpawnHelper import TrsSpawnHelper
from mapadroid.db.helper.WeatherHelper import WeatherHelper
from mapadroid.db.model import (Gym, GymDetail, Pokemon, Pokestop, Raid,
                                TrsEvent, TrsQuest, TrsS2Cell, TrsSpawn,
                                Weather)
from mapadroid.db.PooledQueryExecutor import PooledQueryExecutor
from mapadroid.utils.gamemechanicutil import (gen_despawn_timestamp,
                                              is_mon_ditto)
from mapadroid.utils.logging import get_origin_logger
from mapadroid.utils.questGen import questtask
from mapadroid.utils.s2Helper import S2Helper
from loguru import logger


class DbPogoProtoSubmit:
    """
    Hosts all methods related to submitting protocol data to the database.
    TODO: Most of the code is actually unrelated to database stuff and should be
     moved outside the db package.
    """
    default_spawndef = 240
    # TODO: Redis Cache access needs to be async...

    def __init__(self, db_exec: PooledQueryExecutor, args):
        self._db_exec: PooledQueryExecutor = db_exec
        self._args = args
        self._cache: Optional[Union[Redis, NoopCache]] = None
        # TODO: Async setup

    async def mons(self, session: AsyncSession, origin: str, timestamp: float, map_proto: dict, mitm_mapper):
        """
        Update/Insert mons from a map_proto dict
        """
        cache: Union[Redis, NoopCache] = await self._db_exec.get_cache()

        origin_logger = get_origin_logger(logger, origin=origin)
        origin_logger.debug3("DbPogoProtoSubmit::mons called with data received")
        cells = map_proto.get("cells", None)
        if cells is None:
            return False

        for cell in cells:
            for wild_mon in cell["wild_pokemon"]:
                spawnid = int(str(wild_mon["spawnpoint_id"]), 16)
                lat = wild_mon["latitude"]
                lon = wild_mon["longitude"]
                mon_id = wild_mon["pokemon_data"]["id"]
                encounter_id = wild_mon["encounter_id"]

                if encounter_id < 0:
                    encounter_id = encounter_id + 2 ** 64

                await mitm_mapper.collect_mon_stats(origin, str(encounter_id))

                now = datetime.utcfromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S")

                # get known spawn end time and feed into despawn time calculation
                #getdetspawntime = self._get_detected_endtime(str(spawnid))
                spawnpoint: Optional[TrsSpawn] = await TrsSpawnHelper.get(session, spawnid)
                despawn_time_unix = gen_despawn_timestamp(spawnpoint.calc_endminsec if spawnpoint else None, timestamp)
                despawn_time = datetime.utcfromtimestamp(despawn_time_unix)

                if spawnpoint is None:
                    origin_logger.debug3("adding mon (#{}) at {}, {}. Despawns at {} (init) ({})", mon_id, lat, lon,
                                         despawn_time.strftime("%Y-%m-%d %H:%M:%S"), spawnid)
                else:
                    origin_logger.debug3("adding mon (#{}) at {}, {}. Despawns at {} (non-init) ({})", mon_id, lat, lon,
                                         despawn_time.strftime("%Y-%m-%d %H:%M:%S"), spawnid)

                cache_key = "mon{}".format(encounter_id)
                if await cache.exists(cache_key):
                    continue
                async with session.begin_nested() as nested_transaction:
                    mon: Optional[Pokemon] = await PokemonHelper.get(session, encounter_id)
                    if not mon:
                        mon: Pokemon = Pokemon()
                        mon.encounter_id = encounter_id
                        mon.spawnpoint_id = spawnid
                        mon.latitude = lat
                        mon.longitude = lon
                    else:
                        await session.merge(mon)
                    mon.pokemon_id = mon_id
                    mon.disappear_time = despawn_time
                    mon.gender = wild_mon["pokemon_data"]["display"]["gender_value"]
                    mon.weather_boosted_condition = wild_mon["pokemon_data"]["display"]["weather_boosted_value"]
                    mon.costume = wild_mon["pokemon_data"]["display"]["costume_value"]
                    mon.form = wild_mon["pokemon_data"]["display"]["form_value"]
                    mon.last_modified = datetime.utcnow()
                    try:
                        session.add(mon)
                        await nested_transaction.commit()
                        cache_time = int(despawn_time_unix - int(datetime.now().timestamp()))
                        if cache_time > 0:
                            await cache.set(cache_key, 1, expire=cache_time)
                    except sqlalchemy.exc.IntegrityError as e:
                        logger.warning("Failed committing mon {} ({})", encounter_id, str(e))
                        await nested_transaction.rollback()
        return True

    async def mon_iv(self, session: AsyncSession, origin: str, timestamp: float, encounter_proto: dict, mitm_mapper):
        """
        Update/Insert a mon with IVs
        """
        cache: Union[Redis, NoopCache] = await self._db_exec.get_cache()
        origin_logger = get_origin_logger(logger, origin=origin)
        wild_pokemon = encounter_proto.get("wild_pokemon", None)
        if wild_pokemon is None or wild_pokemon.get("encounter_id", 0) == 0 or not str(wild_pokemon["spawnpoint_id"]):
            return False

        origin_logger.debug3("Updating IV sent for encounter at {}", timestamp)

        now = datetime.utcfromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S")

        spawnid = int(str(wild_pokemon["spawnpoint_id"]), 16)
        spawnpoint: Optional[TrsSpawn] = await TrsSpawnHelper.get(session, spawnid)
        despawn_time_unix = gen_despawn_timestamp(spawnpoint.calc_endminsec if spawnpoint else None, timestamp)
        despawn_time = datetime.utcfromtimestamp(despawn_time_unix)

        latitude = wild_pokemon.get("latitude")
        longitude = wild_pokemon.get("longitude")
        pokemon_data = wild_pokemon.get("pokemon_data")
        encounter_id = wild_pokemon["encounter_id"]
        shiny = wild_pokemon["pokemon_data"]["display"].get("is_shiny", 0)
        pokemon_display = pokemon_data.get("display", {})
        weather_boosted = pokemon_display.get('weather_boosted_value', None)

        if encounter_id < 0:
            encounter_id = encounter_id + 2 ** 64

        cache_key = "moniv{}{}".format(encounter_id, weather_boosted)
        if await cache.exists(cache_key):
            return True

        await mitm_mapper.collect_mon_iv_stats(origin, encounter_id, int(shiny))

        if spawnpoint is None:
            origin_logger.debug3("updating IV mon #{} at {}, {}. Despawning at {} (init)", pokemon_data["id"], latitude,
                                 longitude, despawn_time)
        else:
            origin_logger.debug3("updating IV mon #{} at {}, {}. Despawning at {} (non-init)", pokemon_data["id"],
                                 latitude, longitude, despawn_time)

        capture_probability = encounter_proto.get("capture_probability")
        capture_probability_list = capture_probability.get("capture_probability_list")
        if capture_probability_list is not None:
            capture_probability_list = capture_probability_list.replace("[", "").replace("]", "").split(",")

        # ditto detector
        if is_mon_ditto(origin_logger, pokemon_data):
            # mon must be a ditto :D
            mon_id = 132
            gender = 3
            move_1 = 242
            move_2 = 133
            form = 0
        else:
            mon_id = pokemon_data.get("id")
            gender = pokemon_display.get("gender_value", None)
            move_1 = pokemon_data.get("move_1")
            move_2 = pokemon_data.get("move_2")
            form = pokemon_display.get("form_value", None)
        attempts = 0
        while attempts < 3:
            async with session.begin_nested() as nested_transaction:
                try:
                    mon: Optional[Pokemon] = await PokemonHelper.get(session, encounter_id)
                    if not mon:
                        mon: Pokemon = Pokemon()
                        mon.encounter_id = encounter_id
                        mon.spawnpoint_id = spawnid
                        mon.latitude = latitude
                        mon.longitude = longitude
                    else:
                        await session.refresh(mon)
                    mon.pokemon_id = mon_id
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
                    mon.last_modified = datetime.utcnow()
                    mon.disappear_time = despawn_time

                    session.add(mon)
                    await nested_transaction.commit()
                    cache_time = int(despawn_time_unix - int(datetime.now().timestamp()))
                    if cache_time > 0:
                        await cache.set(cache_key, 1, expire=cache_time)
                    break
                except sqlalchemy.exc.IntegrityError as e:
                    logger.warning("Failed committing mon IV {} ({})", encounter_id, str(e))
                    await nested_transaction.rollback()
                    await asyncio.sleep(0.5)
            attempts += 1

        origin_logger.success("Done updating mon IV in DB")

        return True

    async def spawnpoints(self, session: AsyncSession, origin: str, map_proto: dict, proto_dt: datetime):
        origin_logger = get_origin_logger(logger, origin=origin)
        origin_logger.debug3("DbPogoProtoSubmit::spawnpoints called with data received")
        cells = map_proto.get("cells", None)
        if cells is None:
            return False
        spawn_ids = []
        dt = proto_dt
        for cell in cells:
            for wild_mon in cell["wild_pokemon"]:
                spawn_ids.append(int(str(wild_mon['spawnpoint_id']), 16))

        spawndef: Dict[int, TrsSpawn] = await self._get_spawndef(session, spawn_ids)
        current_event: Optional[TrsEvent] = await TrsEventHelper.get_current_event(session, True)
        spawns_do_add: List[TrsSpawn] = []
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
                    fulldate = dt + timedelta(milliseconds=despawntime)
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
                    spawn.last_scanned = datetime.utcnow()
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
                    spawn.last_non_scanned = datetime.utcnow()
                spawns_do_add.append(spawn)
        session.add_all(spawns_do_add)

    async def stops(self, session: AsyncSession, origin: str, map_proto: dict):
        """
        Update/Insert pokestops from a map_proto dict
        """
        cache: Union[Redis, NoopCache] = await self._db_exec.get_cache()
        origin_logger = get_origin_logger(logger, origin=origin)
        origin_logger.debug3("DbPogoProtoSubmit::stops called with data received")
        cells = map_proto.get("cells", None)
        if cells is None:
            return False

        for cell in cells:
            for fort in cell["forts"]:
                if fort["type"] == 1:
                    await self._handle_pokestop_data(session, cache, fort)
        return True

    async def stop_details(self, session: AsyncSession, stop_proto: dict):
        """
        Update/Insert pokestop details from a GMO
        :param stop_proto:
        :return:

        Args:
            session:
        """
        cache: Union[Redis, NoopCache] = await self._db_exec.get_cache()
        logger.debug3("DbPogoProtoSubmit::pokestops_details called")

        stop: Optional[Pokestop] = await self._extract_args_single_stop_details(session, stop_proto)
        if stop:
            alt_modified_time = int(math.ceil(datetime.utcnow().timestamp() / 1000)) * 1000
            cache_key = "stopdetail{}{}".format(stop.pokestop_id,
                                                stop_proto.get("last_modified_timestamp_ms", alt_modified_time))
            if await cache.exists(cache_key):
                return True
            async with session.begin_nested() as nested_transaction:
                try:
                    await session.merge(stop)
                    await nested_transaction.commit()
                    await cache.set(cache_key, 1, expire=900)
                except sqlalchemy.exc.IntegrityError as e:
                    logger.warning("Failed committing stop details of {} ({})", stop.pokestop_id, str(e))
                    await nested_transaction.rollback()
        return stop is not None

    async def quest(self, session: AsyncSession, origin: str, quest_proto: dict, mitm_mapper):
        origin_logger = get_origin_logger(logger, origin=origin)
        origin_logger.debug3("DbPogoProtoSubmit::quest called")
        fort_id = quest_proto.get("fort_id", None)
        if fort_id is None:
            return False
        if "challenge_quest" not in quest_proto:
            return False
        protoquest = quest_proto["challenge_quest"]["quest"]
        rewards = protoquest.get("quest_rewards", None)
        if rewards is None or not rewards:
            return False
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

        if reward_type == 4:
            item_amount = reward.get('candy', {}).get('amount', 0)
            pokemon_id = reward.get('candy', {}).get('pokemon_id', 0)
        elif reward_type == 12:
            item_amount = reward.get('mega_resource', {}).get('amount', 0)
            pokemon_id = reward.get('mega_resource', {}).get('pokemon_id', 0)

        stardust = reward.get("stardust", None)
        form_id = encounter.get("pokemon_display", {}).get("form_value", 0)
        costume_id = encounter.get("pokemon_display", {}).get("costume_value", 0)
        target = goal.get("target", None)
        condition = goal.get("condition", None)

        json_condition = json.dumps(condition)
        task = questtask(int(quest_type), json_condition, int(target), str(quest_template))

        await mitm_mapper.collect_quest_stats(origin, fort_id)

        quest: Optional[TrsQuest] = await TrsQuestHelper.get(session, fort_id)
        if not quest:
            quest = TrsQuest()
            quest.GUID = fort_id
        quest.quest_type = quest_type
        quest.quest_timestamp = datetime.utcnow()
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

        origin_logger.debug3("DbPogoProtoSubmit::quest submitted quest type {} at stop {}", quest_type, fort_id)
        async with session.begin_nested() as nested_transaction:
            try:
                await session.merge(quest)
                await nested_transaction.commit()
            except sqlalchemy.exc.IntegrityError as e:
                logger.warning("Failed committing quest of stop {}, ({})", fort_id, str(e))
                await nested_transaction.rollback()
        return True

    async def gyms(self, session: AsyncSession, origin: str, map_proto: dict):
        """
        Update/Insert gyms from a map_proto dict
        """
        cache: Union[Redis, NoopCache] = await self._db_exec.get_cache()
        origin_logger = get_origin_logger(logger, origin=origin)
        origin_logger.debug3("DbPogoProtoSubmit::gyms called with data received from")
        cells = map_proto.get("cells", None)
        if cells is None:
            return False
        for cell in cells:
            for gym in cell["forts"]:
                if gym["type"] == 0:
                    guard_pokemon_id = gym["gym_details"]["guard_pokemon"]
                    gymid = gym["id"]
                    team_id = gym["gym_details"]["owned_by_team"]
                    latitude = gym["latitude"]
                    longitude = gym["longitude"]
                    slots_available = gym["gym_details"]["slots_available"]
                    last_modified_ts = gym["last_modified_timestamp_ms"] / 1000
                    last_modified = datetime.utcfromtimestamp(
                        last_modified_ts)
                    is_ex_raid_eligible = gym["gym_details"]["is_ex_raid_eligible"]
                    is_ar_scan_eligible = gym["is_ar_scan_eligible"]

                    cache_key = "gym{}{}".format(gymid, last_modified_ts)
                    if await cache.exists(cache_key):
                        continue

                    gym_obj: Optional[Gym] = await GymHelper.get(session, gymid)
                    if not gym_obj:
                        gym_obj: Gym = Gym()
                        gym_obj.gym_id = gymid
                    gym_obj.team_id = team_id
                    gym_obj.guard_pokemon_id = guard_pokemon_id
                    gym_obj.slots_available = slots_available
                    gym_obj.enabled = 1 # TODO: read in proto?
                    gym_obj.latitude = latitude
                    gym_obj.longitude = longitude
                    gym_obj.total_cp = 0 # TODO: Read from proto..
                    gym_obj.is_in_battle = 0
                    gym_obj.last_modified = last_modified
                    gym_obj.last_scanned = datetime.utcnow()
                    gym_obj.is_ex_raid_eligible = is_ex_raid_eligible
                    gym_obj.is_ar_scan_eligible = is_ar_scan_eligible
                    await session.merge(gym_obj)

                    gym_detail: Optional[GymDetail] = await GymDetailHelper.get(session, gymid)
                    if not gym_detail:
                        gym_detail: GymDetail = GymDetail()
                        gym_detail.gym_id = gymid
                        gym_detail.name = "unknown"
                    gym_detail.url = gym.get("image_url", "")
                    gym_detail.last_scanned = datetime.utcnow()
                    await session.merge(gym_detail)
                    async with session.begin_nested() as nested_transaction:
                        try:
                            await cache.set(cache_key, 1, expire=900)
                            await nested_transaction.commit()
                        except sqlalchemy.exc.IntegrityError as e:
                            logger.warning("Failed committing gym data of {} ({})", gymid, str(e))
                            await nested_transaction.rollback()
        return True

    async def gym(self, session: AsyncSession, origin: str, map_proto: dict):
        """
        Update gyms from a map_proto dict
        """
        origin_logger = get_origin_logger(logger, origin=origin)
        origin_logger.debug3("Updating gyms")
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
                    await session.merge(gym_detail)
                    await nested_transaction.commit()
                except sqlalchemy.exc.IntegrityError as e:
                    logger.warning("Failed committing gym info {} ({})", gym_id, str(e))
                    await nested_transaction.rollback()
        return True

    async def raids(self, session: AsyncSession, origin: str, map_proto: dict, mitm_mapper):
        """
        Update/Insert raids from a map_proto dict
        """
        cache: Union[Redis, NoopCache] = await self._db_exec.get_cache()
        origin_logger = get_origin_logger(logger, origin=origin)
        origin_logger.debug3("DbPogoProtoSubmit::raids called with data received")
        cells = map_proto.get("cells", None)
        if cells is None:
            return False
        for cell in cells:
            for gym in cell["forts"]:
                if gym["type"] == 0 and gym["gym_details"]["has_raid"]:
                    gym_has_raid = gym["gym_details"]["raid_info"]["has_pokemon"]
                    if gym_has_raid:
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

                    raidend_date = datetime.utcfromtimestamp(
                        float(raid_end_sec)).strftime("%Y-%m-%d %H:%M:%S")
                    raidspawn_date = datetime.utcfromtimestamp(float(raid_spawn_sec)).strftime(
                        "%Y-%m-%d %H:%M:%S")
                    raidstart_date = datetime.utcfromtimestamp(float(raid_battle_sec)).strftime(
                        "%Y-%m-%d %H:%M:%S")

                    is_exclusive = gym["gym_details"]["raid_info"]["is_exclusive"]
                    level = gym["gym_details"]["raid_info"]["level"]
                    gymid = gym["id"]

                    await mitm_mapper.collect_raid_stats(origin, gymid)

                    origin_logger.debug3("Adding/Updating gym {} with level {} ending at {}", gymid, level,
                                         raidend_date)

                    cache_key = "raid{}{}{}".format(gymid, pokemon_id, raid_end_sec)
                    if await cache.exists(cache_key):
                        continue

                    raid: Optional[Raid] = await RaidHelper.get(session, gymid)
                    if not raid:
                        raid: Raid = Raid()
                        raid.gym_id = gymid
                    raid.level = level
                    raid.spawn = raidspawn_date
                    raid.start = raidstart_date
                    raid.end = raidend_date
                    raid.pokemon_id = pokemon_id
                    raid.cp = cp
                    raid.move_1 = move_1
                    raid.move_2 = move_2
                    raid.last_scanned = datetime.utcnow()
                    raid.form = form
                    raid.is_exclusive = is_exclusive
                    raid.gender = gender
                    raid.costume = costume
                    raid.evolution = evolution
                    async with session.begin_nested() as nested_transaction:
                        try:
                            await session.merge(raid)

                            await nested_transaction.commit()
                            await cache.set(cache_key, 1, expire=900)
                        except sqlalchemy.exc.IntegrityError as e:
                            logger.warning("Failed committing raid for gym {} ({})", gymid, str(e))
                            await nested_transaction.rollback()
        origin_logger.debug3("DbPogoProtoSubmit::raids: Done submitting raids with data received")
        return True

    async def weather(self, session: AsyncSession, origin, map_proto, received_timestamp) -> bool:
        """
        Update/Insert weather from a map_proto dict
        """
        cache: Union[Redis, NoopCache] = await self._db_exec.get_cache()
        origin_logger = get_origin_logger(logger, origin=origin)
        origin_logger.debug3("DbPogoProtoSubmit::weather called with data received")
        cells = map_proto.get("cells", None)
        if cells is None:
            return False

        for client_weather in map_proto["client_weather"]:
            time_of_day = map_proto.get("time_of_day_value", 0)
            await self._handle_weather_data(session, cache, client_weather, time_of_day, received_timestamp)
        return True

    async def cells(self, session: AsyncSession, origin: str, map_proto: dict):
        protocells = map_proto.get("cells", [])
        cache: Union[Redis, NoopCache] = await self._db_exec.get_cache()

        for cell in protocells:
            cell_id = cell["id"]

            if cell_id < 0:
                cell_id = cell_id + 2 ** 64
            cache_key = "s2cell{}".format(cell_id)
            if await cache.exists(cache_key):
                continue

            lat, lng, _ = S2Helper.get_position_from_cell(cell_id)

            s2cell: Optional[TrsS2Cell] = await TrsS2CellHelper.get(session, cell_id)
            if not s2cell:
                s2cell: TrsS2Cell = TrsS2Cell()
                s2cell.level = 15
                s2cell.center_latitude = lat
                s2cell.center_longitude = lng
            s2cell.updated = cell["current_timestamp"] / 1000
            async with session.begin_nested() as nested_transaction:
                try:
                    await session.merge(s2cell)
                    # Only update s2cell's current_timestamp every 30s at most to avoid too many UPDATE operations
                    # in dense areas being covered by a number of devices
                    await cache.set(cache_key, 1, expire=30)
                except sqlalchemy.exc.IntegrityError as e:
                    logger.warning("Failed committing cell for gym {} ({})", cell_id, str(e))
                    await nested_transaction.rollback()

    async def _handle_pokestop_data(self, session: AsyncSession, cache: NoopCache, stop_data) -> Optional[Pokestop]:
        if stop_data["type"] != 1:
            logger.info("{} is not a pokestop", stop_data)
            return
        alt_modified_time = int(math.ceil(datetime.utcnow().timestamp() / 1000)) * 1000
        cache_key = "stop{}{}".format(stop_data["id"], stop_data.get("last_modified_timestamp_ms", alt_modified_time))
        if await cache.exists(cache_key):
            return

        now = datetime.utcfromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S")
        last_modified = datetime.utcfromtimestamp(
            stop_data["last_modified_timestamp_ms"] / 1000
        )
        lure = "1970-01-01 00:00:00"
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
            lure = datetime.utcfromtimestamp(
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
                incident_start = datetime.utcfromtimestamp(start_ms / 1000).strftime("%Y-%m-%d %H:%M:%S")

            if expiration_ms > 0:
                incident_expiration = datetime.utcfromtimestamp(expiration_ms / 1000).strftime(
                    "%Y-%m-%d %H:%M:%S")
        elif "pokestop_display" in stop_data:
            start_ms = stop_data["pokestop_display"]["incident_start_ms"]
            expiration_ms = stop_data["pokestop_display"]["incident_expiration_ms"]
            incident_grunt_type = stop_data["pokestop_display"]["character_display"]["character"]

            if start_ms > 0:
                incident_start = datetime.utcfromtimestamp(start_ms / 1000).strftime("%Y-%m-%d %H:%M:%S")

            if expiration_ms > 0:
                incident_expiration = datetime.utcfromtimestamp(expiration_ms / 1000).strftime(
                    "%Y-%m-%d %H:%M:%S")
        stop_id = stop_data["id"]

        pokestop: Optional[Pokestop] = await PokestopHelper.get(session, stop_id)
        if not pokestop:
            pokestop: Pokestop = Pokestop()
            pokestop.pokestop_id = stop_id
        pokestop.enabled = 1 # TODO: Shouldn't this be in the proto?
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
        async with session.begin_nested() as nested_transaction:
            try:
                await session.merge(pokestop)
                await nested_transaction.commit()
                await cache.set(cache_key, 1, expire=900)
            except sqlalchemy.exc.IntegrityError as e:
                logger.warning("Failed committing stop {} ({})", stop_id, str(e))
                await nested_transaction.rollback()

    async def _extract_args_single_stop_details(self, session: AsyncSession, stop_data) -> Optional[Pokestop]:
        if stop_data.get("type", 999) != 1:
            return None
        image = stop_data.get("image_urls", None)
        name = stop_data.get("name", None)
        now = datetime.utcnow()
        stop_id = stop_data["fort_id"]
        pokestop: Optional[Pokestop] = await PokestopHelper.get(session, stop_id)
        if not pokestop:
            pokestop: Pokestop = Pokestop()
            pokestop.pokestop_id = stop_data["id"]
            pokestop.enabled = 1  # TODO: Shouldn't this be in the proto?
            pokestop.last_modified = datetime.utcfromtimestamp(stop_data.get("last_modified_timestamp_ms", 0) / 1000)
        pokestop.latitude = stop_data["latitude"]
        pokestop.longitude = stop_data["longitude"]
        pokestop.name = name
        pokestop.image = image
        pokestop.last_updated = now
        return pokestop

    async def _handle_weather_data(self, session: AsyncSession, cache: NoopCache, client_weather_data, time_of_day,
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
        if await cache.exists(cache_key):
            return
        async with session.begin_nested() as nested_transaction:
            try:
                weather: Optional[Weather] = await WeatherHelper.get(session, cell_id)
                if not weather:
                    weather: Weather = Weather()
                    weather.s2_cell_id = cell_id
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
                weather.last_updated = datetime.utcnow()

                if not weather:
                    return

                await session.merge(weather)
                await cache.set(cache_key, 1, expire=900)
                await nested_transaction.commit()
            except sqlalchemy.exc.IntegrityError as e:
                logger.warning("Failed committing weather of cell {} ({})", cell_id, str(e))
                await nested_transaction.rollback()

    async def _get_spawndef(self, session: AsyncSession, spawn_ids) -> Dict[int, TrsSpawn]:
        if not spawn_ids:
            return {}
        logger.debug3("DbPogoProtoSubmit::_get_spawndef called")

        spawnret = {}
        res: List[TrsSpawn] = await TrsSpawnHelper.get_all(session, spawn_ids)
        for spawn in res:
            spawnret[int(spawn.spawnpoint)] = spawn
        return spawnret

    def _get_current_spawndef_pos(self):
        minute_value = int(datetime.now().strftime("%M"))
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
