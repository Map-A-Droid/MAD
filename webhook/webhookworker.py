import json
import time
from typing import Optional, List

import requests

from db.DbWebhookReader import DbWebhookReader
from geofence.geofenceHelper import GeofenceHelper
from utils.MappingManager import MappingManager
from utils.gamemechanicutil import calculate_mon_level, get_raid_boss_cp
from utils.logging import logger
from utils.madGlobals import terminate_mad
from utils.questGen import generate_quest
from utils.s2Helper import S2Helper


class WebhookWorker:
    __IV_MON: List[int] = List[int]
    __excluded_areas = {}

    def __init__(self, args, data_manager, mapping_manager: MappingManager, rarity, db_webhook_reader: DbWebhookReader):
        self.__worker_interval_sec = 10
        self.__args = args
        self.__data_manager = data_manager
        self.__db_wrapper = self.__data_manager.dbc
        self._db_reader = db_webhook_reader
        self.__rarity = rarity
        self.__last_check = int(time.time())

        self.__build_ivmon_list(mapping_manager)
        self.__build_excluded_areas(mapping_manager)

        if self.__args.webhook_start_time != 0:
            self.__last_check = int(self.__args.webhook_start_time)

    def update_settings(self, mapping_manager: MappingManager):
        self.__build_ivmon_list(mapping_manager)
        self.__build_excluded_areas(mapping_manager)

    def __payload_type_count(self, payload):
        count = {}

        for elem in payload:
            count[elem["type"]] = count.get(elem["type"], 0) + 1

        return count

    def __payload_chunk(self, payload, size):
        if size == 0:
            return [payload]

        return [payload[x: x + size] for x in range(0, len(payload), size)]

    def __is_in_excluded_area(self, coordinate):
        for gfh in self.__excluded_areas:
            if gfh.is_coord_inside_include_geofence(coordinate):
                return True

        return False

    def __send_webhook(self, payload):
        if len(payload) == 0:
            logger.debug("Payload empty. Skip sending to webhook.")
            return

        # get list of urls
        webhooks = self.__args.webhook_url.replace(" ", "").split(",")

        webhook_count = len(webhooks)
        current_wh_num = 1

        for webhook in webhooks:
            payloadToSend = []
            subTypes = "all"
            url = webhook.strip()

            if url.startswith("["):
                endIndex = webhook.rindex("]")
                endIndex += 1
                subTypes = webhook[:endIndex]
                url = url[endIndex:]

                for payloadData in payload:
                    if payloadData["type"] in subTypes:
                        payloadToSend.append(payloadData)
            else:
                payloadToSend = payload

            if len(payloadToSend) == 0:
                logger.debug(
                    "Payload empty. Skip sending to: {} (Filter: {})", url, subTypes
                )
                continue
            else:
                logger.debug("Sending to webhook url: {} (Filter: {})", url, subTypes)

            payload_list = self.__payload_chunk(
                payloadToSend, self.__args.webhook_max_payload_size
            )

            current_pl_num = 1
            for payload_chunk in payload_list:
                logger.debug4("Python data for payload: {}", str(payload_chunk))
                logger.debug3("Payload: {}", str(json.dumps(payload_chunk)))

                try:
                    response = requests.post(
                        url,
                        data=json.dumps(payload_chunk),
                        headers={"Content-Type": "application/json"},
                        timeout=5,
                    )

                    if response.status_code != 200:
                        logger.warning(
                            "Got status code other than 200 OK from webhook destination: {}",
                            str(response.status_code),
                        )
                    else:
                        if webhook_count > 1:
                            whcount_text = " [wh {}/{}]".format(
                                current_wh_num, webhook_count
                            )
                        else:
                            whcount_text = ""

                        if len(payload_list) > 1:
                            whchunk_text = " [pl {}/{}]".format(
                                current_pl_num, len(payload_list)
                            )
                        else:
                            whchunk_text = ""

                        logger.success(
                            "Successfully sent payload to webhook{}{}. Stats: {}",
                            whchunk_text,
                            whcount_text,
                            json.dumps(self.__payload_type_count(payload_chunk)),
                        )
                except Exception as e:
                    logger.warning(
                        "Exception occured while sending webhook: {}", str(e)
                    )

                current_pl_num += 1
            current_wh_num += 1

    def __prepare_quest_data(self, quest_data):
        ret = []
        for stopid in quest_data:
            stop = quest_data[str(stopid)]

            if self.__is_in_excluded_area([stop["latitude"], stop["longitude"]]):
                continue

            try:
                quest = generate_quest(quest_data[str(stopid)])
                quest_payload = self.__construct_quest_payload(quest)

                entire_payload = {"type": "quest", "message": quest_payload}
                ret.append(entire_payload)
            except Exception as e:
                logger.error(
                    "Exception occured while generating quest webhook: {}", str(e)
                )

        return ret

    def __construct_quest_payload(self, quest):
        if self.__args.quest_webhook_flavor == "default":
            return {
                "pokestop_id": quest["pokestop_id"],
                "latitude": quest["latitude"],
                "longitude": quest["longitude"],
                "quest_type": quest["quest_type"],
                "quest_type_raw": quest["quest_type_raw"],
                "item_type": quest["item_type"],
                "name": quest["name"].replace('"', '\\"').replace("\n", "\\n"),
                "url": quest["url"],
                "timestamp": quest["timestamp"],
                "quest_reward_type": quest["quest_reward_type"],
                "quest_reward_type_raw": quest["quest_reward_type_raw"],
                "quest_target": quest["quest_target"],
                "pokemon_id": int(quest["pokemon_id"]),
                "pokemon_form": int(quest["pokemon_form"]),
                "pokemon_costume": int(quest.get("pokemon_costume", '0')),
                "item_amount": quest["item_amount"],
                "item_id": quest["item_id"],
                "quest_task": quest["quest_task"],
                "quest_condition": quest["quest_condition"].replace("'", '"').lower(),
                "quest_template": quest["quest_template"],
            }

        # Other known type is Poracle/RDM compatible.

        # For some reason we aren't saving JSON in our databse, so we gotta replace ' with ".
        # Pray that we never save strings that contain ' inside them.
        quest_conditions = json.loads(quest["quest_condition"].replace("'", '"'))
        quest_condition = []
        quest_rewards = []
        a_quest_type = quest["quest_reward_type_raw"]
        a_quest_reward = {}
        quest_rewards.append(a_quest_reward)
        a_quest_reward["info"] = {}
        a_quest_reward["type"] = a_quest_type

        if a_quest_type == 2:
            a_quest_reward["info"]["item_id"] = quest["item_id"]
            a_quest_reward["info"]["amount"] = int(quest["item_amount"])
        if a_quest_type == 3:
            a_quest_reward["info"]["amount"] = int(quest["item_amount"])
        if a_quest_type == 7:
            a_quest_reward["info"]["pokemon_id"] = int(quest["pokemon_id"])
            a_quest_reward["info"]["pokemon_form"] = int(quest["pokemon_form"])
            a_quest_reward["info"]["pokemon_costume"] = int(quest.get("pokemon_costume", '0'))
            a_quest_reward["info"]["shiny"] = 0
            a_quest_reward["info"]["form"] = int(quest["pokemon_form"])

        for a_quest_condition in quest_conditions:
            # Quest condition for special type of pokemon.
            if "with_pokemon_type" in a_quest_condition:
                a_quest_condition["info"] = a_quest_condition.pop("with_pokemon_type")
                a_quest_condition["info"]["pokemon_type_ids"] = a_quest_condition[
                    "info"
                ].pop("pokemon_type")
            # Quest condition for raid level(s).
            if "with_raid_level" in a_quest_condition:
                a_quest_condition["info"] = a_quest_condition.pop("with_raid_level")
                a_quest_condition["info"]["raid_levels"] = a_quest_condition[
                    "info"
                ].pop("raid_level")
            # Quest condition for throw type.
            if "with_throw_type" in a_quest_condition:
                a_quest_condition["info"] = a_quest_condition.pop("with_throw_type")
                a_quest_condition["info"]["throw_type_id"] = a_quest_condition[
                    "info"
                ].pop("throw_type")
            # Quest condition for use of special items
            if "with_item" in a_quest_condition:
                a_quest_condition["info"] = a_quest_condition.pop("with_item")
                a_quest_condition["info"]["item_id"] = a_quest_condition["info"].pop(
                    "item"
                )
            # Quest condition for catching specific mons.
            if "with_pokemon_category" in a_quest_condition:
                a_quest_condition["info"] = a_quest_condition.pop("with_pokemon_category")

            quest_condition.append(a_quest_condition)

        return {
            "pokestop_id": quest["pokestop_id"],
            "pokestop_name": quest["name"].replace('"', '\\"').replace("\n", "\\n"),
            "template": quest["quest_template"],
            "pokestop_url": quest["url"],
            "conditions": quest_condition,
            "type": quest["quest_type_raw"],
            "latitude": quest["latitude"],
            "longitude": quest["longitude"],
            "rewards": quest_rewards,
            "target": quest["quest_target"],
            "timestamp": quest["timestamp"],
            "quest_task": quest["quest_task"],
        }

    def __prepare_weather_data(self, weather_data):
        ret = []

        for weather in weather_data:
            weather_payload = {
                "s2_cell_id": weather["s2_cell_id"],
                "condition": weather["gameplay_weather"],
                "alert_severity": weather["severity"],
                "day": weather["world_time"],
                "time_changed": weather["last_updated"],
            }

            if weather.get("latitude", None) is None:
                weather_payload["latitude"] = S2Helper.middle_of_cell(
                    weather["s2_cell_id"]
                )[0]
            else:
                weather_payload["latitude"] = weather["latitude"]

            if weather.get("longitude", None) is None:
                weather_payload["longitude"] = S2Helper.middle_of_cell(
                    weather["s2_cell_id"]
                )[1]
            else:
                weather_payload["longitude"] = weather["longitude"]

            if weather.get("coords", None) is None:
                weather_payload["coords"] = S2Helper.coords_of_cell(
                    weather["s2_cell_id"]
                )
            else:
                weather_payload["coords"] = weather["coords"]

            entire_payload = {"type": "weather", "message": weather_payload}
            ret.append(entire_payload)

        return ret

    def __prepare_raid_data(self, raid_data):
        ret = []

        for raid in raid_data:
            if self.__is_in_excluded_area([raid["latitude"], raid["longitude"]]):
                continue

            # skip ex raid mon if disabled
            is_exclusive = (
                raid["is_exclusive"] is not None and raid["is_exclusive"] != 0
            )
            if not self.__args.webhook_submit_exraids and is_exclusive:
                continue

            raid_payload = {
                "latitude": raid["latitude"],
                "longitude": raid["longitude"],
                "level": raid["level"],
                "pokemon_id": raid["pokemon_id"],
                "team_id": raid["team_id"],
                "cp": raid["cp"],
                "start": raid["start"],
                "end": raid["end"],
                "name": raid["name"],
            }

            if raid["move_1"] is not None:
                raid_payload["move_1"] = raid["move_1"]

            if raid["move_2"] is not None:
                raid_payload["move_2"] = raid["move_2"]

            if raid["cp"] is None:
                raid_payload["cp"] = get_raid_boss_cp(raid["pokemon_id"])

            if raid["pokemon_id"] is None:
                raid_payload["pokemon_id"] = 0

            if raid["gym_id"] is not None:
                raid_payload["gym_id"] = raid["gym_id"]

            if raid["url"] is not None and raid["url"]:
                raid_payload["url"] = raid["url"]

            if raid["weather_boosted_condition"] is not None:
                raid_payload["weather"] = raid["weather_boosted_condition"]

            if raid["form"] is not None:
                raid_payload["form"] = raid["form"]

            if raid["is_ex_raid_eligible"] is not None:
                raid_payload["is_ex_raid_eligible"] = raid["is_ex_raid_eligible"]

            if raid["is_exclusive"] is not None:
                raid_payload["is_exclusive"] = raid["is_exclusive"]

            if raid["gender"] is not None:
                raid_payload["gender"] = raid["gender"]

            if raid["costume"] is not None:
                raid_payload["costume"] = raid["costume"]

            # create final message
            entire_payload = {"type": "raid", "message": raid_payload}

            # add to payload
            ret.append(entire_payload)

        return ret

    def __prepare_mon_data(self, mon_data):
        ret = []

        for mon in mon_data:
            if self.__is_in_excluded_area([mon["latitude"], mon["longitude"]]):
                continue

            if (
                not self.__args.pokemon_webhook_nonivs
                and mon["pokemon_id"] in self.__IV_MON
                and (mon["individual_attack"] is None)
            ):
                # skipping this mon since IV has not been scanned yet
                continue

            mon_payload = {
                "encounter_id": mon["encounter_id"],
                "pokemon_id": mon["pokemon_id"],
                "spawnpoint_id": mon["spawnpoint_id"],
                "latitude": mon["latitude"],
                "longitude": mon["longitude"],
                "disappear_time": mon["disappear_time"],
                "verified": mon["spawn_verified"],
            }

            # get rarity
            pokemon_rarity = self.__rarity.rarity_by_id(pokemonid=mon["pokemon_id"])

            if mon.get("cp_multiplier", None) is not None:
                mon_payload["cp_multiplier"] = mon["cp_multiplier"]
                mon_payload["pokemon_level"] = calculate_mon_level(mon["cp_multiplier"])

            if mon["form"] is not None and mon["form"] > 0:
                mon_payload["form"] = mon["form"]

            if mon["costume"] is not None:
                mon_payload["costume"] = mon["costume"]

            if mon["cp"] is not None:
                mon_payload["cp"] = mon["cp"]

            if mon["individual_attack"] is not None:
                mon_payload["individual_attack"] = mon["individual_attack"]

            if mon["individual_defense"] is not None:
                mon_payload["individual_defense"] = mon["individual_defense"]

            if mon["individual_stamina"] is not None:
                mon_payload["individual_stamina"] = mon["individual_stamina"]

            if mon["move_1"] is not None:
                mon_payload["move_1"] = mon["move_1"]

            if mon["move_2"] is not None:
                mon_payload["move_2"] = mon["move_2"]

            if mon.get("height", None) is not None:
                mon_payload["height"] = mon["height"]

            if mon["weight"] is not None:
                mon_payload["weight"] = mon["weight"]

            if mon["gender"] is not None:
                mon_payload["gender"] = mon["gender"]

            if pokemon_rarity is not None:
                mon_payload["rarity"] = pokemon_rarity

            if (
                mon["weather_boosted_condition"] is not None
                and mon["weather_boosted_condition"] > 0
            ):
                if self.__args.quest_webhook_flavor == "default":
                    mon_payload["boosted_weather"] = mon["weather_boosted_condition"]
                if self.__args.quest_webhook_flavor == "poracle":
                    mon_payload["weather"] = mon["weather_boosted_condition"]

            entire_payload = {"type": "pokemon", "message": mon_payload}
            ret.append(entire_payload)

        return ret

    def __prepare_gyms_data(self, gym_data):
        ret = []

        for gym in gym_data:
            if self.__is_in_excluded_area([gym["latitude"], gym["longitude"]]):
                continue

            gym_payload = {
                "gym_id": gym["gym_id"],
                "latitude": gym["latitude"],
                "longitude": gym["longitude"],
                "team_id": gym["team_id"],
                "name": gym["name"],
                "slots_available": gym["slots_available"],
            }

            if gym.get("description", None) is not None:
                gym_payload["description"] = gym.get("description")

            if gym["url"] is not None:
                gym_payload["url"] = gym["url"]

            if gym["is_ex_raid_eligible"] is not None:
                gym_payload["is_ex_raid_eligible"] = gym["is_ex_raid_eligible"]

            entire_payload = {"type": "gym", "message": gym_payload}
            ret.append(entire_payload)

        return ret

    def __prepare_stops_data(self, pokestop_data):
        ret = []

        for pokestop in pokestop_data:
            if self.__is_in_excluded_area([pokestop["latitude"], pokestop["longitude"]]):
                continue

            pokestop_payload = {
                "name": pokestop["name"],
                "pokestop_id": pokestop["pokestop_id"],
                "latitude": pokestop["latitude"],
                "longitude": pokestop["longitude"],
                "updated": pokestop["last_updated"],
                "last_modified": pokestop["last_modified"]
            }

            if 'active_fort_modifier' in pokestop and pokestop["active_fort_modifier"]:
                pokestop_payload["lure_expiration"] = pokestop["lure_expiration"]
                pokestop_payload["lure_id"] = pokestop["active_fort_modifier"]

            if pokestop["image"]:
                pokestop_payload["url"] = pokestop["image"]

            if pokestop["incident_start"]:
                pokestop_payload["incident_start"] = pokestop["incident_start"]

            if pokestop["incident_expiration"]:
                pokestop_payload["incident_expiration"] = pokestop["incident_expiration"]

            if pokestop["incident_grunt_type"]:
                pokestop_payload["incident_grunt_type"] = pokestop["incident_grunt_type"]

            entire_payload = {"type": "pokestop", "message": pokestop_payload}
            ret.append(entire_payload)

        return ret

    def __build_ivmon_list(self, mapping_manager: MappingManager):
        self.__IV_MON: List[int] = []

        for routemanager_name in mapping_manager.get_all_routemanager_names():
            ids_iv_list: Optional[List[int]] = mapping_manager.routemanager_get_ids_iv(routemanager_name)

            if ids_iv_list is not None:
                # TODO check if area/routemanager is actually active before adding the IDs
                self.__IV_MON = self.__IV_MON + list(set(ids_iv_list) - set(self.__IV_MON))

    def __build_excluded_areas(self, mapping_manager: MappingManager):
        self.__excluded_areas: List[GeofenceHelper] = []

        if self.__args.webhook_excluded_areas == "":
            pass

        tmp_excluded_areas = {}
        for rm in mapping_manager.get_all_routemanager_names():
            name = mapping_manager.routemanager_get_name(rm)
            gfh = mapping_manager.routemanager_get_geofence_helper(rm)
            tmp_excluded_areas[name] = gfh

        area_names = self.__args.webhook_excluded_areas.split(",")
        for area_name in area_names:
            for name, gf in tmp_excluded_areas.items():
                if (area_name.endswith("*") and name.startswith(area_name[:-1])) or area_name == name:
                    self.__excluded_areas.append(gf)

        tmp_excluded_areas = None

        if len(self.__excluded_areas) > 0:
            logger.info("Excluding {} areas from webhooks", len(self.__excluded_areas))

    def __create_payload(self):
        logger.debug("Fetching data changed since {}", self.__last_check)

        # the payload that is about to be sent
        full_payload = []

        try:
            # raids
            raids = self.__prepare_raid_data(
                self._db_reader.get_raids_changed_since(self.__last_check)
            )
            full_payload += raids

            # quests
            if self.__args.quest_webhook:
                quest = self.__prepare_quest_data(
                    self._db_reader.get_quests_changed_since(self.__last_check)
                )
                full_payload += quest

            # weather
            if self.__args.weather_webhook:
                weather = self.__prepare_weather_data(
                    self._db_reader.get_weather_changed_since(self.__last_check)
                )
                full_payload += weather

            # gyms
            if self.__args.gym_webhook:
                gyms = self.__prepare_gyms_data(
                    self._db_reader.get_gyms_changed_since(self.__last_check)
                )
                full_payload += gyms

            # stops
            if self.__args.pokestop_webhook:
                pokestops = self.__prepare_stops_data(
                    self._db_reader.get_stops_changed_since(self.__last_check)
                )
                full_payload += pokestops

            # mon
            if self.__args.pokemon_webhook:
                mon = self.__prepare_mon_data(
                    self._db_reader.get_mon_changed_since(self.__last_check)
                )
                full_payload += mon
        except Exception:
            logger.exception("Error while creating webhook payload")

        logger.debug2("Done fetching data + building payload")

        return full_payload

    def run_worker(self):
        logger.info("Starting webhook worker thread")

        while not terminate_mad.is_set():
            preparing_timestamp = int(time.time())

            # fetch data and create payload
            full_payload = self.__create_payload()

            # send our payload
            self.__send_webhook(full_payload)

            self.__last_check = preparing_timestamp
            time.sleep(self.__worker_interval_sec)

        logger.info("Stopping webhook worker thread")
