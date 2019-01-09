import asyncio
import functools
import json
import logging
from threading import current_thread, Event, Thread

import requests
from s2sphere import Cell, CellId, LatLng

log = logging.getLogger(__name__)

raid_webhook_payload = """[{{
      "message": {{
        "latitude": {lat},
        "longitude": {lon},
        "level": {lvl},
        "pokemon_id": "{poke_id}",
        "team": {team},
        "cp": "{cp}",
        "move_1": {move_1},
        "move_2": {move_2},
        "raid_begin": {hatch_time},
        "raid_end": {end},
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
        "team": {team},
        "raid_begin": {hatch_time},
        "raid_end": {end},
        "gym_id": "{ext_id}",
        "name": "{name_id}",
        "url": "{url}",
        "sponsor": "{sponsor}",
        "weather": "{weather}",
        "park": "{park}"
      }},
      "type": "{type}"
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

pokemon_webhook_payload = """[{{
  "message": {{
    "encounter_id": {id},
    "pokemon_id": "{pokemon_id}",
    "last_modified_time": {now} ,
    "spawnpoint_id": {spawnid},
    "latitude": {lat},
    "longitude": {lon},
    "disappear_time": {despawn_time_unix},
    "time_until_hidden_ms": {tth}
  }},
  "type": "pokemon"
}}]"""

gym_webhook_payload = """[{{
  "message": {{
    "raid_active_until": {raid_active_until},
    "gym_id": "{gym_id}",
    "gym_name": "{gym_name}",
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
        with open('pokemon.json') as j:
            self.pokemon_file = json.load(j)
        self.gyminfo = None

        self.loop = None
        self.loop_started = Event()
        self.loop_tid = None
        self.t_asyncio_loop = Thread(name='webhook_asyncio_loop', target=self.__start_asyncio_loop)
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
            return f()  # We can call directly if we're not going between threads.
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
                    log.warning("Got status code other than 200 OK from webhook destination: %s" % str(response.status_code))
                else:
                    log.info("Success sending webhook")
            except Exception as e:
                log.warning("Exception occured while sending webhook: %s" % str(e))

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
            self.__add_task_to_loop(self._send_weather_webhook(s2_cell_id, weather_id, severe, warn, day, time))

    def submit_pokemon_webhook(self, id, pokemon_id, now, spawnid, lat, lon, despawn_time_unix):
        if self.__application_args.webhook and self.__application_args.pokemon_webhook:
            self.__add_task_to_loop(self._submit_pokemon_webhook(id, pokemon_id, now, spawnid,
                                                                 lat, lon, despawn_time_unix))

    def send_gym_webhook(self, gym_id, raid_active_until, gym_name, team_id, slots_available, guard_pokemon_id,
                         latitude, longitude):
        if self.__application_args.webhook and self.__application_args.gym_webhook:
            self.__add_task_to_loop(self._send_gym_webhook(gym_id, raid_active_until, gym_name, team_id,
                                    slots_available, guard_pokemon_id, latitude, longitude))

    async def _send_gym_webhook(self, gym_id, raid_active_until, gym_name, team_id,
                                slots_available, guard_pokemon_id, latitude, longitude):
        info_of_gym = self.gyminfo.get(gym_id, None)
        if info_of_gym is not None and gym_name == 'unknown':
            name = info_of_gym.get("name", "unknown")
            gym_name = name.replace("\\", r"\\").replace('"', '')

        payload_raw = gym_webhook_payload.format(
            raid_active_until=raid_active_until,
            gym_id=gym_id,
            gym_name=gym_name,
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
                        description = info_of_gym["description"]\
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

            data = weather_webhook_payload.format(s2cellId, coords, weatherId, severe, warn, day, time, latitude, longitude)

            log.debug(data)
            payload = json.loads(data)
            self.__sendToWebhook(payload)
        else:
            log.debug("Weather Webhook Disabled")

    async def _submit_pokemon_webhook(self, id, pokemon_id, now, spawnid, lat, lon, despawn_time_unix):
        log.info('Sending Pokemon %s (#%s) to webhook', pokemon_id, id)

        tth = despawn_time_unix - now

        data = pokemon_webhook_payload.format(
            id=id,
            pokemon_id=pokemon_id,
            now=now,
            spawnid=spawnid,
            lat=lat,
            lon=lon,
            despawn_time_unix=despawn_time_unix,
            tth=tth)

        log.debug(data)
        payload = json.loads(data)
        self.__sendToWebhook(payload)
