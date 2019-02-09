import asyncio
import functools
import json
import logging
import os
from threading import Event, Thread, current_thread

import requests

from s2sphere import Cell, CellId, LatLng
from utils.language import open_json_file
from utils.questGen import generate_quest

log = logging.getLogger(__name__)

raid_webhook_payload = """[{{
      "message": {{
        "latitude": {lat},
        "longitude": {lon},
        "level": {lvl},
        "pokemon_id": "{poke_id}",
        "team_id": {team},
        "cp": "{cp}",
        "move_1": {move_1},
        "move_2": {move_2},
        "start": {hatch_time},
        "end": {end},
        "gym_id": "{ext_id}",
        "name": "{name_id}",
        "url": "{url}",
        "sponsor": "{sponsor}",
        "weather": "{weather}",
        "park": "{park}"
      }},
      "type": "{type}"
   }} ]"""

egg_webhook_payload = """[{{
      "message": {{
        "latitude": {lat},
        "longitude": {lon},
        "level": {lvl},
        "team_id": {team},
        "start": {hatch_time},
        "end": {end},
        "gym_id": "{ext_id}",
        "name": "{name_id}",
        "url": "{url}",
        "pokemon_id": 0,
        "sponsor": "{sponsor}",
        "weather": "{weather}",
        "park": "{park}"
      }},
      "type": "{type}"
   }} ]"""

quest_webhook_payload = """[{{
      "message": {{
                "pokestop_id": "{pokestop_id}",
                "latitude": "{latitude}",
                "longitude": "{longitude}",
                "quest_type": "{quest_type}",
                "quest_type_raw": "{quest_type_raw}",
                "item_type": "{item_type}",
                "item_amount": "{item_amount}",
                "item_id": "{item_id}",
                "pokemon_id": "{pokemon_id}",
                "name": "{name}",
                "url": "{url}",
                "timestamp": "{timestamp}",
                "quest_reward_type": "{quest_reward_type}",
                "quest_reward_type_raw": "{quest_reward_type_raw}",
                "quest_target": "{quest_target}",
                "quest_task": "{quest_task}",
                "quest_condition": "{quest_condition}"
        }},
      "type": "quest"
   }} ]"""


weather_webhook_payload = """[{{
      "message": {{
                "s2_cell_id": {0},
                "coords": {1},
                "condition": {2},
                "alert_severity": {3},
                "warn": {4},
                "day": {5},
                "time_changed": {6},
                "latitude": {7},
                "longitude": {8}
        }},
      "type": "weather"
   }} ]"""

plain_webhook = """[{plain}]"""

gym_webhook_payload = """[{{
  "message": {{
    "raid_active_until": {raid_active_until},
    "gym_id": "{gym_id}",
    "name": "{gym_name}",
    "description": "{gym_description}",
    "url": "{gym_url}",
    "team_id": {team_id},
    "slots_available": {slots_available},
    "guard_pokemon_id": {guard_pokemon_id},
    "lowest_pokemon_motivation": {lowest_pokemon_motivation},
    "total_cp": {total_cp},
    "enabled": "True",
    "latitude": {latitude},
    "longitude": {longitude}
  }},
  "type": "gym"
}}]"""


class WebhookHelper(object):
    def __init__(self, args):
        self.__application_args = args
        self.pokemon_file = None
        self.pokemon_file = open_json_file('pokemon')
        self.gyminfo = None

        self.loop = None
        self.loop_started = Event()
        self.loop_tid = None
        self.t_asyncio_loop = Thread(
            name='webhook_asyncio_loop', target=self.__start_asyncio_loop)
        self.t_asyncio_loop.daemon = True
        self.t_asyncio_loop.start()

    def set_gyminfo(self, db_wrapper):
        try:
            with open('gym_info.json') as f:
                self.gyminfo = json.load(f)
        except FileNotFoundError as e:
            log.warning("gym_info.json not found")
            if db_wrapper is not None:
                log.info("Trying to create gym_info.json")
                db_wrapper.download_gym_infos()
                with open('gym_info.json') as f:
                    self.gyminfo = json.load(f)

    def __start_asyncio_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop_tid = current_thread()
        self.loop.call_soon(self.loop_started.set)
        self.loop.run_forever()

    def __add_task_to_loop(self, coro):
        f = functools.partial(self.loop.create_task, coro)
        if current_thread() == self.loop_tid:
            # We can call directly if we're not going between threads.
            return f()
        else:
            return self.loop.call_soon_threadsafe(f)

    def __stop_loop(self):
        self.loop.call_soon_threadsafe(self.loop.stop)

    def __sendToWebhook(self, payload):
        webhooks = self.__application_args.webhook_url.split(',')

        for webhook in webhooks:
            url = webhook.strip()

            log.debug("Sending to webhook %s", url)
            log.debug("Payload: %s" % str(payload))
            try:
                response = requests.post(
                    url, data=json.dumps(payload),
                    headers={'Content-Type': 'application/json'},
                    timeout=5
                )
                if response.status_code != 200:
                    log.warning(
                        "Got status code other than 200 OK from webhook destination: %s" % str(response.status_code))
                else:
                    log.info("Success sending webhook")
            except Exception as e:
                log.warning(
                    "Exception occured while sending webhook: %s" % str(e))

    def get_raid_boss_cp(self, mon_id):
        if self.pokemon_file is not None and int(mon_id) > 0:
            log.debug("Removing leading zero from string where necessary")
            mon_id = int(mon_id)

            if 'cp' in self.pokemon_file[str(mon_id)]:
                log.debug("CP found for pokemon_id: " + str(mon_id) + " with the value of " + str(
                    self.pokemon_file[str(mon_id)]["cp"]))
                return self.pokemon_file[str(mon_id)]["cp"]
            else:
                log.warning("No raid cp found for " + str(mon_id))
                return '0'
        else:
            log.debug("No CP returns as its an egg!")
            return '0'

    def send_raid_webhook(self, gymid, type, start, end, lvl, mon,
                          team_param=None, cp_param=None, move1_param=None, move2_param=None,
                          name_param="unknown", lat_param=None, lng_param=None, weather_param=None,
                          image_url=None):
        if self.__application_args.webhook:
            self.__add_task_to_loop(self._send_raid_webhook(gymid, type, start, end, lvl, mon,
                                                            team_param=team_param, cp_param=cp_param,
                                                            move1_param=move1_param, move2_param=move2_param,
                                                            name_param=name_param,
                                                            lat_param=lat_param, lng_param=lng_param,
                                                            weather_param=weather_param,
                                                            image_url=image_url))

    def send_weather_webhook(self, s2_cell_id, weather_id, severe, warn, day, time):
        if self.__application_args.webhook and self.__application_args.weather_webhook:
            self.__add_task_to_loop(self._send_weather_webhook(
                s2_cell_id, weather_id, severe, warn, day, time))

    def send_pokemon_webhook(self, encounter_id, pokemon_id, last_modified_time, spawnpoint_id, lat, lon,
                             despawn_time_unix,
                             pokemon_level=None, cp_multiplier=None, form=None, cp=None,
                             individual_attack=None, individual_defense=None, individual_stamina=None,
                             move_1=None, move_2=None, height=None, weight=None):
        if self.__application_args.webhook and self.__application_args.pokemon_webhook:
            self.__add_task_to_loop(self._submit_pokemon_webhook(encounter_id=encounter_id, pokemon_id=pokemon_id,
                                                                 last_modified_time=last_modified_time,
                                                                 spawnpoint_id=spawnpoint_id, lat=lat, lon=lon,
                                                                 despawn_time_unix=despawn_time_unix,
                                                                 pokemon_level=pokemon_level,
                                                                 cp_multiplier=cp_multiplier,
                                                                 form=form, cp=cp,
                                                                 individual_attack=individual_attack,
                                                                 individual_defense=individual_defense,
                                                                 individual_stamina=individual_stamina,
                                                                 move_1=move_1, move_2=move_2,
                                                                 height=height, weight=weight)
                                    )

    def submit_quest_webhook(self, rawquest):
        if self.__application_args.webhook:
            self.__add_task_to_loop(self._submit_quest_webhook(rawquest))

    def send_gym_webhook(self, gym_id, raid_active_until, gym_name, team_id, slots_available, guard_pokemon_id,
                         latitude, longitude):
        if self.__application_args.webhook and self.__application_args.gym_webhook:
            self.__add_task_to_loop(self._send_gym_webhook(gym_id, raid_active_until, gym_name, team_id,
                                                           slots_available, guard_pokemon_id, latitude, longitude))

    async def _send_gym_webhook(self, gym_id, raid_active_until, gym_name, team_id,
                                slots_available, guard_pokemon_id, latitude, longitude):
        info_of_gym = self.gyminfo.get(gym_id, None)
        gym_url = 'unknown'
        gym_description = 'unknown'
        if info_of_gym is not None and gym_name == 'unknown':
            name = info_of_gym.get("name", "unknown")
            gym_name = name.replace("\\", r"\\").replace('"', '')
            gym_description = info_of_gym.get('description', 'unknown')\
                .replace('\\', r'\\').replace('"', '')
            gym_url = info_of_gym.get('url', 'unknown')\
                .replace('\\', r'\\').replace('"', '')

        payload_raw = gym_webhook_payload.format(
            raid_active_until=raid_active_until,
            gym_id=gym_id,
            gym_name=gym_name,
            gym_description=gym_description,
            gym_url=gym_url,
            team_id=team_id,
            slots_available=slots_available,
            guard_pokemon_id=guard_pokemon_id,
            lowest_pokemon_motivation=0,
            total_cp=0,
            latitude=latitude,
            longitude=longitude
        )

        payload = json.loads(payload_raw)
        self.__sendToWebhook(payload)

    async def _send_raid_webhook(self, gymid, type, start, end, lvl, mon,
                                 team_param=None, cp_param=None, move1_param=None, move2_param=None,
                                 name_param="unknown", lat_param=None, lng_param=None, weather_param=None,
                                 image_url=None):
        log.info('Start preparing values for webhook')
        if mon is None:
            poke_id = 0
        else:
            poke_id = mon

        form = 0
        park = 0
        description = ""
        sponsor = 0

        wtype = "raid"

        if team_param is not None:
            team = str(team_param)
        else:
            team = '0'

        if cp_param is not None:
            cp = str(cp_param)
        else:
            cp = self.get_raid_boss_cp(poke_id)

        if move1_param is not None:
            move_1 = str(move1_param)
        else:
            move_1 = '1'

        if move2_param is not None:
            move_2 = str(move2_param)
        else:
            move_2 = '1'

        if name_param is not None and name_param != "unknown":
            # gym name cleanup
            name = name_param.replace('"', r'\"')
        else:
            name = "unknown"

        if lat_param is not None:
            lat = str(lat_param)
        else:
            lat = '0'

        if lng_param is not None:
            lng = str(lng_param)
        else:
            lng = '0'

        if weather_param is not None:
            weather = weather_param
        else:
            weather = 0

        if image_url is None:
            image_url = "0"

        if self.gyminfo is not None:
            info_of_gym = self.gyminfo.get(gymid, None)
            if info_of_gym is not None:
                name = info_of_gym.get("name", "unknown")
                if name is not None:
                    name = name.replace("\\", r"\\").replace('"', '')
                else:
                    name = "unknown"
                lat = info_of_gym["latitude"]
                lng = info_of_gym["longitude"]
                image_url = info_of_gym["url"]
                if info_of_gym["description"]:
                    try:
                        description = info_of_gym["description"] \
                            .replace("\\", r"\\").replace('"', '').replace("\n", "")
                    except (ValueError, TypeError) as e:
                        description = ""
                if 'park' in self.gyminfo[str(gymid)]:
                    try:
                        park = int(info_of_gym.get("park", 0))
                    except (ValueError, TypeError) as e:
                        park = None
                if 'sponsor' in self.gyminfo[str(gymid)]:
                    try:
                        sponsor = int(info_of_gym.get("sponsor", 0))
                    except (ValueError, TypeError) as e:
                        sponsor = 0

        hatch_time = int(start)
        end = int(end)

        if poke_id == 0 or poke_id is None:
            payload_raw = egg_webhook_payload.format(
                ext_id=gymid,
                lat=lat,
                lon=lng,
                name_id=name,
                sponsor=sponsor,
                lvl=lvl,
                end=end,
                hatch_time=hatch_time,
                team=team,
                type=wtype,
                url=image_url,
                description=description,
                park=park,
                weather=weather
            )
        else:
            payload_raw = raid_webhook_payload.format(
                ext_id=gymid,
                lat=lat,
                lon=lng,
                name_id=name,
                sponsor=sponsor,
                poke_id=poke_id,
                lvl=lvl,
                end=end,
                hatch_time=hatch_time,
                move_1=move_1,
                move_2=move_2,
                cp=cp,
                form=form,
                team=team,
                type=wtype,
                url=image_url,
                description=description,
                park=park,
                weather=weather
            )

        payload = json.loads(payload_raw)
        self.__sendToWebhook(payload)

    async def _send_weather_webhook(self, s2cellId, weatherId, severe, warn, day, time):
        if self.__application_args.weather_webhook:
            log.debug("Send Weather Webhook")

            ll = CellId(s2cellId).to_lat_lng()
            latitude = ll.lat().degrees
            longitude = ll.lng().degrees

            cell = Cell(CellId(s2cellId))
            coords = []
            for v in range(0, 4):
                vertex = LatLng.from_point(cell.get_vertex(v))
                coords.append([vertex.lat().degrees, vertex.lng().degrees])

            data = weather_webhook_payload.format(
                s2cellId, coords, weatherId, severe, warn, day, time, latitude, longitude)

            log.debug(data)
            payload = json.loads(data)
            self.__sendToWebhook(payload)
        else:
            log.debug("Weather Webhook Disabled")

    async def _submit_pokemon_webhook(self, encounter_id, pokemon_id, last_modified_time, spawnpoint_id, lat, lon,
                                      despawn_time_unix,
                                      pokemon_level=None, cp_multiplier=None, form=None, cp=None,
                                      individual_attack=None, individual_defense=None, individual_stamina=None,
                                      move_1=None, move_2=None, height=None, weight=None):
        log.info('Sending Pokemon %s (#%s) to webhook', pokemon_id, id)

        mon_payload = {"encounter_id": encounter_id, "pokemon_id": pokemon_id, "last_modified_time": last_modified_time,
                       "spawnpoint_id": spawnpoint_id, "latitude": lat, "longitude": lon,
                       "disappear_time": despawn_time_unix}
        tth = despawn_time_unix - last_modified_time
        mon_payload["time_until_hidden_ms"] = tth

        if pokemon_level is not None:
            mon_payload["pokemon_level"] = pokemon_level

        if cp_multiplier is not None:
            mon_payload["cp_multiplier"] = cp_multiplier

        if form is not None:
            mon_payload["form"] = form

        if cp is not None:
            mon_payload["cp"] = cp

        if individual_attack is not None:
            mon_payload["individual_attack"] = individual_attack

        if individual_defense is not None:
            mon_payload["individual_defense"] = individual_defense

        if individual_stamina is not None:
            mon_payload["individual_stamina"] = individual_stamina

        if move_1 is not None:
            mon_payload["move_1"] = move_1

        if move_2 is not None:
            mon_payload["move_2"] = move_2

        if height is not None:
            mon_payload["height"] = height

        if weight is not None:
            mon_payload["weight"] = weight

        entire_payload = {"type": "pokemon", "message": mon_payload}
        to_be_sent = json.dumps(entire_payload, indent=4, sort_keys=True)
        to_be_sent = plain_webhook.format(plain=to_be_sent)
        to_be_sent = json.loads(to_be_sent)

        self.__sendToWebhook(to_be_sent)

    async def _submit_quest_webhook(self, rawquest):
        log.info('Sending Quest to webhook')

        for pokestopid in rawquest:
            quest = generate_quest(rawquest[str(pokestopid)])

        data = quest_webhook_payload.format(
            pokestop_id=quest['pokestop_id'],
            latitude=quest['latitude'],
            longitude=quest['longitude'],
            quest_type=quest['quest_type'],
            quest_type_raw=quest['quest_type_raw'],
            item_type=quest['item_type'],
            name=quest['name'].replace('"', '\\"').replace('\n', '\\n'),
            url=quest['url'],
            timestamp=quest['timestamp'],
            quest_reward_type=quest['quest_reward_type'],
            quest_reward_type_raw=quest['quest_reward_type_raw'],
            quest_target=quest['quest_target'],
            pokemon_id=quest['pokemon_id'],
            item_amount=quest['item_amount'],
            item_id=quest['item_id'],
            quest_task=quest['quest_task'],
            quest_condition=quest['quest_condition'])

        payload = json.loads(data)
        self.__sendToWebhook(payload)
