import json
import time
from datetime import datetime, timedelta
from bitstring import BitArray
from mapadroid.db.PooledQueryExecutor import PooledQueryExecutor
from mapadroid.utils.gamemechanicutil import gen_despawn_timestamp, is_mon_ditto
from mapadroid.utils.questGen import questtask
from mapadroid.utils.s2Helper import S2Helper
from mapadroid.utils.logging import get_logger, LoggerEnums, get_origin_logger


logger = get_logger(LoggerEnums.database)


class DbPogoProtoSubmit:
    """
    Hosts all methods related to submitting protocol data to the database.
    TODO: Most of the code is actually unrelated to database stuff and should be
    moved outside the db package.
    """
    default_spawndef = 240

    def __init__(self, db_exec: PooledQueryExecutor):
        self._db_exec: PooledQueryExecutor = db_exec

    def mons(self, origin: str, map_proto: dict, mitm_mapper):
        """
        Update/Insert mons from a map_proto dict
        """
        origin_logger = get_origin_logger(logger, origin=origin)
        origin_logger.debug3("DbPogoProtoSubmit::mons called with data received")
        cells = map_proto.get("cells", None)
        if cells is None:
            return False

        query_mons = (
            "INSERT INTO pokemon (encounter_id, spawnpoint_id, pokemon_id, latitude, longitude, disappear_time, "
            "individual_attack, individual_defense, individual_stamina, move_1, move_2, cp, cp_multiplier, "
            "weight, height, gender, catch_prob_1, catch_prob_2, catch_prob_3, rating_attack, rating_defense, "
            "weather_boosted_condition, last_modified, costume, form) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
            "%s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE last_modified=VALUES(last_modified), disappear_time=VALUES(disappear_time)"
        )

        mon_args = []
        for cell in cells:
            for wild_mon in cell["wild_pokemon"]:
                spawnid = int(str(wild_mon["spawnpoint_id"]), 16)
                lat = wild_mon["latitude"]
                lon = wild_mon["longitude"]
                mon_id = wild_mon["pokemon_data"]["id"]
                encounter_id = wild_mon["encounter_id"]

                if encounter_id < 0:
                    encounter_id = encounter_id + 2 ** 64

                mitm_mapper.collect_mon_stats(origin, str(encounter_id))

                now = datetime.utcfromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S")

                # get known spawn end time and feed into despawn time calculation
                getdetspawntime = self._get_detected_endtime(str(spawnid))
                despawn_time_unix = gen_despawn_timestamp(getdetspawntime)
                despawn_time = datetime.utcfromtimestamp(despawn_time_unix).strftime("%Y-%m-%d %H:%M:%S")

                if getdetspawntime is None:
                    origin_logger.debug3("adding mon (#{}) at {}, {}. Despawns at {} (init) ({})", mon_id, lat, lon,
                                         despawn_time, spawnid)
                else:
                    origin_logger.debug3("adding mon (#{}) at {}, {}. Despawns at {} (non-init) ({})", mon_id, lat, lon,
                                         despawn_time, spawnid)

                mon_args.append(
                    (
                        encounter_id, spawnid, mon_id, lat, lon,
                        despawn_time,
                        # TODO: consider .get("XXX", None)
                        None, None, None, None, None, None, None, None, None,
                        wild_mon["pokemon_data"]["display"]["gender_value"],
                        None, None, None, None, None,
                        wild_mon["pokemon_data"]["display"]["weather_boosted_value"],
                        now, wild_mon["pokemon_data"]["display"]["costume_value"],
                        wild_mon["pokemon_data"]["display"]["form_value"]
                    )
                )

        self._db_exec.executemany(query_mons, mon_args, commit=True)
        return True

    def mon_iv(self, origin: str, timestamp: float, encounter_proto: dict, mitm_mapper):
        """
        Update/Insert a mon with IVs
        """
        origin_logger = get_origin_logger(logger, origin=origin)
        wild_pokemon = encounter_proto.get("wild_pokemon", None)
        if wild_pokemon is None or wild_pokemon.get("encounter_id", 0) == 0 or not str(wild_pokemon["spawnpoint_id"]):
            return

        origin_logger.debug3("Updating IV sent for encounter at {}", timestamp)

        now = datetime.utcfromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S")

        spawnid = int(str(wild_pokemon["spawnpoint_id"]), 16)

        getdetspawntime = self._get_detected_endtime(str(spawnid))
        despawn_time_unix = gen_despawn_timestamp(getdetspawntime)
        despawn_time = datetime.utcfromtimestamp(despawn_time_unix).strftime("%Y-%m-%d %H:%M:%S")

        latitude = wild_pokemon.get("latitude")
        longitude = wild_pokemon.get("longitude")
        pokemon_data = wild_pokemon.get("pokemon_data")
        encounter_id = wild_pokemon["encounter_id"]
        shiny = wild_pokemon["pokemon_data"]["display"].get("is_shiny", 0)

        if encounter_id < 0:
            encounter_id = encounter_id + 2 ** 64

        mitm_mapper.collect_mon_iv_stats(origin, encounter_id, int(shiny))

        if getdetspawntime is None:
            origin_logger.debug3("updating IV mon #{} at {}, {}. Despawning at {} (init)", pokemon_data["id"], latitude,
                                 longitude, despawn_time)
        else:
            origin_logger.debug3("updating IV mon #{} at {}, {}. Despawning at {} (non-init)", pokemon_data["id"],
                                 latitude, longitude, despawn_time)

        capture_probability = encounter_proto.get("capture_probability")
        capture_probability_list = capture_probability.get("capture_probability_list")
        if capture_probability_list is not None:
            capture_probability_list = capture_probability_list.replace("[", "").replace("]", "").split(",")

        pokemon_display = pokemon_data.get("display", {})

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

        query = (
            "INSERT INTO pokemon (encounter_id, spawnpoint_id, pokemon_id, latitude, longitude, disappear_time, "
            "individual_attack, individual_defense, individual_stamina, move_1, move_2, cp, cp_multiplier, "
            "weight, height, gender, catch_prob_1, catch_prob_2, catch_prob_3, rating_attack, rating_defense, "
            "weather_boosted_condition, last_modified, costume, form) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
            "%s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE last_modified=VALUES(last_modified), disappear_time=VALUES(disappear_time), "
            "individual_attack=VALUES(individual_attack), individual_defense=VALUES(individual_defense), "
            "individual_stamina=VALUES(individual_stamina), move_1=VALUES(move_1), move_2=VALUES(move_2), "
            "cp=VALUES(cp), cp_multiplier=VALUES(cp_multiplier), weight=VALUES(weight), height=VALUES(height), "
            "gender=VALUES(gender), catch_prob_1=VALUES(catch_prob_1), catch_prob_2=VALUES(catch_prob_2), "
            "catch_prob_3=VALUES(catch_prob_3), rating_attack=VALUES(rating_attack), "
            "rating_defense=VALUES(rating_defense), weather_boosted_condition=VALUES(weather_boosted_condition), "
            "costume=VALUES(costume), form=VALUES(form), pokemon_id=VALUES(pokemon_id)"
        )
        insert_values = (
            encounter_id,
            spawnid,
            mon_id,
            latitude, longitude, despawn_time,
            pokemon_data.get("individual_attack"),
            pokemon_data.get("individual_defense"),
            pokemon_data.get("individual_stamina"),
            move_1,
            move_2,
            pokemon_data.get("cp"),
            pokemon_data.get("cp_multiplier"),
            pokemon_data.get("weight"),
            pokemon_data.get("height"),
            gender,
            float(capture_probability_list[0]),
            float(capture_probability_list[1]),
            float(capture_probability_list[2]),
            None, None,
            pokemon_display.get('weather_boosted_value', None),
            now,
            pokemon_display.get("costume_value", None),
            form
        )

        self._db_exec.execute(query, insert_values, commit=True)
        origin_logger.debug3("Done updating mon in DB")
        return True

    def spawnpoints(self, origin: str, map_proto: dict, proto_dt: datetime):
        origin_logger = get_origin_logger(logger, origin=origin)
        origin_logger.debug3("DbPogoProtoSubmit::spawnpoints called with data received")
        cells = map_proto.get("cells", None)
        if cells is None:
            return False
        spawnpoint_args, spawnpoint_args_unseen = [], []
        spawn_ids = []

        query_spawnpoints = (
            "INSERT INTO trs_spawn (spawnpoint, latitude, longitude, earliest_unseen, "
            "last_scanned, spawndef, calc_endminsec, eventid) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, "
            "(select id from trs_event where now() between event_start and "
            "event_end order by event_start desc limit 1)) "
            "ON DUPLICATE KEY UPDATE "
            "last_scanned=VALUES(last_scanned), "
            "earliest_unseen=LEAST(earliest_unseen, VALUES(earliest_unseen)), "
            "spawndef=if(((select id from trs_event where now() between event_start and event_end order "
            "by event_start desc limit 1)=1 and eventid=1) or (select id from trs_event where now() between "
            "event_start and event_end order by event_start desc limit 1)<>1 and eventid<>1, VALUES(spawndef), "
            "spawndef), "
            "calc_endminsec=VALUES(calc_endminsec)"
        )

        query_spawnpoints_unseen = (
            "INSERT INTO trs_spawn (spawnpoint, latitude, longitude, earliest_unseen, last_non_scanned, spawndef, "
            "eventid) VALUES (%s, %s, %s, %s, %s, %s, "
            "(select id from trs_event where now() between event_start and "
            "event_end order by event_start desc limit 1)) "
            "ON DUPLICATE KEY UPDATE "
            "spawndef=if(((select id from trs_event where now() between event_start and event_end order "
            "by event_start desc limit 1)=1 and eventid=1) or (select id from trs_event where now() between "
            "event_start and event_end order by event_start desc limit 1)<>1 and eventid<>1, VALUES(spawndef), "
            "spawndef), "
            "last_non_scanned=VALUES(last_non_scanned)"
        )

        now = proto_dt.strftime("%Y-%m-%d %H:%M:%S")
        dt = proto_dt

        for cell in cells:
            for wild_mon in cell["wild_pokemon"]:
                spawn_ids.append(int(str(wild_mon['spawnpoint_id']), 16))

        spawndef = self._get_spawndef(spawn_ids)

        for cell in cells:
            for wild_mon in cell["wild_pokemon"]:
                spawnid = int(str(wild_mon["spawnpoint_id"]), 16)
                lat, lng, alt = S2Helper.get_position_from_cell(
                    int(str(wild_mon["spawnpoint_id"]) + "00000", 16))
                despawntime = wild_mon["time_till_hidden"]

                minpos = self._get_current_spawndef_pos()
                # TODO: retrieve the spawndefs by a single executemany and pass that...

                spawndef_ = spawndef.get(spawnid, False)
                if spawndef_:
                    newspawndef = self._set_spawn_see_minutesgroup(spawndef_, minpos)
                else:
                    newspawndef = self._set_spawn_see_minutesgroup(self.default_spawndef, minpos)

                last_scanned = None
                last_non_scanned = None

                if 0 <= int(despawntime) <= 90000:
                    fulldate = dt + timedelta(milliseconds=despawntime)
                    earliest_unseen = int(despawntime)
                    last_scanned = now
                    calcendtime = fulldate.strftime("%M:%S")

                    spawnpoint_args.append(
                        (spawnid, lat, lng, earliest_unseen, last_scanned, newspawndef, calcendtime)
                    )
                else:
                    earliest_unseen = 99999999
                    last_non_scanned = now

                    spawnpoint_args_unseen.append(
                        (spawnid, lat, lng, earliest_unseen, last_non_scanned, newspawndef)
                    )

        self._db_exec.executemany(query_spawnpoints, spawnpoint_args, commit=True)
        self._db_exec.executemany(query_spawnpoints_unseen,
                                  spawnpoint_args_unseen, commit=True)

    def stops(self, origin: str, map_proto: dict):
        """
        Update/Insert pokestops from a map_proto dict
        """
        origin_logger = get_origin_logger(logger, origin=origin)
        origin_logger.debug3("DbPogoProtoSubmit::stops called with data received")
        cells = map_proto.get("cells", None)
        if cells is None:
            return False

        query_stops = (
            "INSERT INTO pokestop (pokestop_id, enabled, latitude, longitude, last_modified, lure_expiration, "
            "last_updated, active_fort_modifier, incident_start, incident_expiration, incident_grunt_type) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE last_updated=VALUES(last_updated), lure_expiration=VALUES(lure_expiration), "
            "last_modified=VALUES(last_modified), latitude=VALUES(latitude), longitude=VALUES(longitude), "
            "active_fort_modifier=VALUES(active_fort_modifier), incident_start=VALUES(incident_start), "
            "incident_expiration=VALUES(incident_expiration), incident_grunt_type=VALUES(incident_grunt_type)"
        )

        stops_args = []
        for cell in cells:
            for fort in cell["forts"]:
                if fort["type"] == 1:
                    stops_args.append(
                        self._extract_args_single_stop(fort))

        self._db_exec.executemany(query_stops, stops_args, commit=True)
        return True

    def stop_details(self, stop_proto: dict):
        """
        Update/Insert pokestop details from a GMO
        :param stop_proto:
        :return:
        """
        logger.debug3("DbPogoProtoSubmit::pokestops_details called")

        query_stops = (
            "INSERT INTO pokestop (pokestop_id, enabled, latitude, longitude, last_modified, "
            "last_updated, name, image) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE last_updated=VALUES(last_updated), lure_expiration=VALUES(lure_expiration), "
            "latitude=VALUES(latitude), longitude=VALUES(longitude), name=VALUES(name), image=VALUES(image)"
        )

        stop_args = self._extract_args_single_stop_details(stop_proto)

        if stop_args is not None:
            self._db_exec.execute(query_stops, stop_args, commit=True)
        return True

    def quest(self, origin: str, quest_proto: dict, mitm_mapper):
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
        stardust = reward.get("stardust", None)
        pokemon_id = encounter.get("pokemon_id", None)
        form_id = encounter.get("pokemon_display", {}).get("form_value", 0)
        costume_id = encounter.get("pokemon_display", {}).get("costume_value", 0)
        target = goal.get("target", None)
        condition = goal.get("condition", None)

        json_condition = json.dumps(condition)
        task = questtask(int(quest_type), json_condition, int(target), str(quest_template))

        mitm_mapper.collect_quest_stats(origin, fort_id)

        query_quests = (
            "INSERT INTO trs_quest (GUID, quest_type, quest_timestamp, quest_stardust, quest_pokemon_id, "
            "quest_pokemon_form_id, quest_pokemon_costume_id, "
            "quest_reward_type, quest_item_id, quest_item_amount, quest_target, quest_condition, quest_reward, "
            "quest_task, quest_template) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            "ON DUPLICATE KEY UPDATE quest_type=VALUES(quest_type), quest_timestamp=VALUES(quest_timestamp), "
            "quest_stardust=VALUES(quest_stardust), quest_pokemon_id=VALUES(quest_pokemon_id), "
            "quest_reward_type=VALUES(quest_reward_type), quest_item_id=VALUES(quest_item_id), "
            "quest_item_amount=VALUES(quest_item_amount), quest_target=VALUES(quest_target), "
            "quest_condition=VALUES(quest_condition), quest_reward=VALUES(quest_reward), "
            "quest_task=VALUES(quest_task), quest_template=VALUES(quest_template), "
            "quest_pokemon_form_id=VALUES(quest_pokemon_form_id), "
            "quest_pokemon_costume_id=VALUES(quest_pokemon_costume_id)"
        )
        insert_values = (
            fort_id, quest_type, time.time(), stardust, pokemon_id, form_id, costume_id, reward_type,
            item_item, item_amount, target,
            json_condition, json.dumps(rewards), task, quest_template
        )
        origin_logger.debug3("DbPogoProtoSubmit::quest submitted quest type {} at stop {}", quest_type, fort_id)
        self._db_exec.execute(query_quests, insert_values, commit=True)

        return True

    def gyms(self, origin: str, map_proto: dict):
        """
        Update/Insert gyms from a map_proto dict
        """
        origin_logger = get_origin_logger(logger, origin=origin)
        origin_logger.debug3("DbPogoProtoSubmit::gyms called with data received from")
        cells = map_proto.get("cells", None)
        if cells is None:
            return False
        gym_args = []
        gym_details_args = []
        now = datetime.utcfromtimestamp(
            time.time()).strftime("%Y-%m-%d %H:%M:%S")

        query_gym = (
            "INSERT INTO gym (gym_id, team_id, guard_pokemon_id, slots_available, enabled, latitude, longitude, "
            "total_cp, is_in_battle, last_modified, last_scanned, is_ex_raid_eligible) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE "
            "guard_pokemon_id=VALUES(guard_pokemon_id), team_id=VALUES(team_id), "
            "slots_available=VALUES(slots_available), last_scanned=VALUES(last_scanned), "
            "last_modified=VALUES(last_modified), latitude=VALUES(latitude), longitude=VALUES(longitude), "
            "is_ex_raid_eligible=VALUES(is_ex_raid_eligible)"
        )
        query_gym_details = (
            "INSERT INTO gymdetails (gym_id, name, url, last_scanned) "
            "VALUES (%s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE last_scanned=VALUES(last_scanned), "
            "url=IF(VALUES(url) IS NOT NULL AND VALUES(url) <> '', VALUES(url), url)"
        )

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
                        last_modified_ts).strftime("%Y-%m-%d %H:%M:%S")
                    is_ex_raid_eligible = gym["gym_details"]["is_ex_raid_eligible"]

                    gym_args.append(
                        (
                            gymid, team_id, guard_pokemon_id, slots_available,
                            1,  # enabled
                            latitude, longitude,
                            0,  # total CP
                            0,  # is_in_battle
                            last_modified,  # last_modified
                            now,  # last_scanned
                            is_ex_raid_eligible
                        )
                    )

                    gym_details_args.append(
                        (gym["id"], "unknown", gym["image_url"], now)
                    )
        self._db_exec.executemany(query_gym, gym_args, commit=True)
        self._db_exec.executemany(query_gym_details, gym_details_args, commit=True)
        origin_logger.debug3("submit_gyms done")
        return True

    def gym(self, origin: str, map_proto: dict):
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

        set_keys = []
        insert_values = []

        if name is not None and name != "":
            set_keys.append("name=%s")
            insert_values.append(name)
        if description is not None and description != "":
            set_keys.append("description=%s")
            insert_values.append(description)
        if url is not None and url != "":
            set_keys.append("url=%s")
            insert_values.append(url)

        if len(set_keys) == 0:
            return False

        query = "UPDATE gymdetails SET " + ",".join(set_keys) + " WHERE gym_id = %s"
        insert_values.append(gym_id)

        self._db_exec.execute((query), tuple(insert_values), commit=True)

        return True

    def raids(self, origin: str, map_proto: dict, mitm_mapper):
        """
        Update/Insert raids from a map_proto dict
        """
        origin_logger = get_origin_logger(logger, origin=origin)
        origin_logger.debug3("DbPogoProtoSubmit::raids called with data received")
        cells = map_proto.get("cells", None)
        if cells is None:
            return False
        raid_args = []
        now = datetime.utcfromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S")

        query_raid = (
            "INSERT INTO raid (gym_id, level, spawn, start, end, pokemon_id, cp, move_1, move_2, last_scanned, form, "
            "is_exclusive, gender, costume) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE level=VALUES(level), spawn=VALUES(spawn), start=VALUES(start), "
            "end=VALUES(end), pokemon_id=VALUES(pokemon_id), cp=VALUES(cp), move_1=VALUES(move_1), "
            "move_2=VALUES(move_2), last_scanned=VALUES(last_scanned), is_exclusive=VALUES(is_exclusive), "
            "form=VALUES(form), gender=VALUES(gender), costume=VALUES(costume)"
        )

        for cell in cells:
            for gym in cell["forts"]:
                if gym["type"] == 0 and gym["gym_details"]["has_raid"]:
                    gym_has_raid = gym["gym_details"]["raid_info"]["has_pokemon"]
                    if gym_has_raid:
                        pokemon_id = gym["gym_details"]["raid_info"]["raid_pokemon"]["id"]
                        cp = gym["gym_details"]["raid_info"]["raid_pokemon"]["cp"]
                        move_1 = gym["gym_details"]["raid_info"]["raid_pokemon"]["move_1"]
                        move_2 = gym["gym_details"]["raid_info"]["raid_pokemon"]["move_2"]
                        form = gym["gym_details"]["raid_info"]["raid_pokemon"]["display"]["form_value"]
                        gender = gym["gym_details"]["raid_info"]["raid_pokemon"]["display"]["gender_value"]
                        costume = gym["gym_details"]["raid_info"]["raid_pokemon"]["display"]["costume_value"]
                    else:
                        pokemon_id = None
                        cp = 0
                        move_1 = 1
                        move_2 = 2
                        form = None
                        gender = None
                        costume = None

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

                    mitm_mapper.collect_raid_stats(origin, gymid)

                    origin_logger.debug3("Adding/Updating gym {} with level {} ending at {}", gymid, level,
                                         raidend_date)

                    raid_args.append(
                        (
                            gymid,
                            level,
                            raidspawn_date,
                            raidstart_date,
                            raidend_date,
                            pokemon_id, cp, move_1, move_2, now,
                            form,
                            is_exclusive,
                            gender,
                            costume
                        )
                    )
        self._db_exec.executemany(query_raid, raid_args, commit=True)
        origin_logger.debug3("DbPogoProtoSubmit::raids: Done submitting raids with data received")
        return True

    def weather(self, origin, map_proto, received_timestamp):
        """
        Update/Insert weather from a map_proto dict
        """
        origin_logger = get_origin_logger(logger, origin=origin)
        origin_logger.debug3("DbPogoProtoSubmit::weather called with data received")
        cells = map_proto.get("cells", None)
        if cells is None:
            return False

        query_weather = (
            "INSERT INTO weather (s2_cell_id, latitude, longitude, cloud_level, rain_level, wind_level, "
            "snow_level, fog_level, wind_direction, gameplay_weather, severity, warn_weather, world_time, "
            "last_updated) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE fog_level=VALUES(fog_level), cloud_level=VALUES(cloud_level), "
            "snow_level=VALUES(snow_level), wind_direction=VALUES(wind_direction), "
            "world_time=VALUES(world_time), gameplay_weather=VALUES(gameplay_weather), "
            "last_updated=VALUES(last_updated)"
        )

        list_of_weather_args = []
        for client_weather in map_proto["client_weather"]:
            # lat, lng, alt = S2Helper.get_position_from_cell(weather_extract["cell_id"])
            time_of_day = map_proto.get("time_of_day_value", 0)
            list_of_weather_args.append(
                self._extract_args_single_weather(
                    client_weather, time_of_day, received_timestamp)
            )
        self._db_exec.executemany(query_weather, list_of_weather_args, commit=True)
        return True

    def cells(self, origin: str, map_proto: dict):
        protocells = map_proto.get("cells", [])

        query = (
            "INSERT INTO trs_s2cells (id, level, center_latitude, center_longitude, updated) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE updated=VALUES(updated)"
        )

        cells = []
        for cell in protocells:
            cell_id = cell["id"]

            if cell_id < 0:
                cell_id = cell_id + 2 ** 64

            lat, lng, alt = S2Helper.get_position_from_cell(cell_id)

            cells.append((cell_id, 15, lat, lng, cell["current_timestamp"] / 1000))

        self._db_exec.executemany(query, cells, commit=True)

    def _extract_args_single_stop(self, stop_data):
        if stop_data["type"] != 1:
            logger.warning("{} is not a pokestop", stop_data)
            return None

        now = datetime.utcfromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S")
        last_modified = datetime.utcfromtimestamp(
            stop_data["last_modified_timestamp_ms"] / 1000
        ).strftime("%Y-%m-%d %H:%M:%S")
        lure = "1970-01-01 00:00:00"
        active_fort_modifier = None
        incident_start = None
        incident_expiration = None
        incident_grunt_type = None

        if len(stop_data["active_fort_modifier"]) > 0:
            # get current lure duration
            sql = "select `event_lure_duration` " \
                  "from trs_event " \
                  "where now() between `event_start` and `event_end` and `event_name`<>'DEFAULT'"
            found = self._db_exec.execute(sql)
            if found and len(found) > 0 and found[0][0]:
                lure_duration = int(found[0][0])
            else:
                lure_duration = int(30)

            active_fort_modifier = stop_data["active_fort_modifier"][0]
            lure = datetime.utcfromtimestamp(
                lure_duration * 60 + (stop_data["last_modified_timestamp_ms"] / 1000)
            ).strftime("%Y-%m-%d %H:%M:%S")

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

        return (stop_data["id"], 1, stop_data["latitude"], stop_data["longitude"],
                last_modified, lure, now, active_fort_modifier,
                incident_start, incident_expiration, incident_grunt_type
                )

    def _extract_args_single_stop_details(self, stop_data):
        if stop_data.get("type", 999) != 1:
            return None
        image = stop_data.get("image_urls", None)
        name = stop_data.get("name", None)
        now = datetime.utcfromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S")
        last_modified = "1970-01-01 00:00:00"

        return (stop_data["fort_id"], 1, stop_data["latitude"], stop_data["longitude"],
                last_modified, now, name, image[0]
                )

    def _extract_args_single_weather(self, client_weather_data, time_of_day, received_timestamp):
        now = datetime.utcfromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S")
        cell_id = client_weather_data["cell_id"]
        real_lat, real_lng = S2Helper.middle_of_cell(cell_id)

        display_weather_data = client_weather_data.get("display_weather", None)
        if display_weather_data is None:
            return None
        else:
            gameplay_weather = client_weather_data["gameplay_weather"]["gameplay_condition"]

        return (
            cell_id, real_lat, real_lng,
            display_weather_data.get("cloud_level", 0),
            display_weather_data.get("rain_level", 0),
            display_weather_data.get("wind_level", 0),
            display_weather_data.get("snow_level", 0),
            display_weather_data.get("fog_level", 0),
            display_weather_data.get("wind_direction", 0),
            gameplay_weather,
            # TODO: alerts
            0, 0,
            time_of_day, now
        )

    def _get_detected_endtime(self, spawn_id):
        logger.debug3("DbPogoProtoSubmit::_get_detected_endtime called")

        query = (
            "SELECT calc_endminsec "
            "FROM trs_spawn "
            "WHERE spawnpoint=%s"
        )
        args = (
            spawn_id,
        )

        found = self._db_exec.execute(query, args)

        if found and len(found) > 0 and found[0][0]:
            return str(found[0][0])
        else:
            return False

    def _get_spawndef(self, spawn_ids):
        if not spawn_ids:
            return False
        logger.debug3("DbPogoProtoSubmit::_get_spawndef called")

        spawnids = ",".join(map(str, spawn_ids))
        spawnret = {}

        query = (
            "SELECT spawnpoint, spawndef "
            "FROM trs_spawn where spawnpoint in (%s)" % (spawnids)
        )
        # vals = (spawn_id,)

        res = self._db_exec.execute(query)
        for row in res:
            spawnret[int(row[0])] = row[1]
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
        # b = BitArray([int(digit) for digit in bin(spawndef)[2:]])
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
