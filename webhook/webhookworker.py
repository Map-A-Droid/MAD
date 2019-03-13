import json
import logging
import requests
import time

from utils.gamemechanicutil import calculate_mon_level
from utils.gamemechanicutil import get_raid_boss_cp
from utils.s2Helper import S2Helper

log = logging.getLogger(__name__)


class WebhookWorker:
    # currently active ex raid mon id
    EXRAID_MON_ID = 386

    def __init__(self, args, db_wrapper):
        self._worker_interval_sec = 10
        self._args = args
        self._db_wrapper = db_wrapper
        self._last_check = int(time.time())

        if self._args.webhook_start_time != 0:
            self._last_check = int(self._args.webhook_start_time)

    def __payload_type_count(self, payload):
        count = {}

        for elem in payload:
            count[elem["type"]] = count.get(elem["type"], 0) + 1

        return count

    def __send_webhook(self, payload):
        if len(payload) == 0:
            log.info("Payload empty. Skip sending to webhook.")
            return


        # get list of urls
        webhooks = self._args.webhook_url.replace(" ", "").split(",")

        for webhook in webhooks:
            payloadToSend = []
            # url cleanup
            url = webhook.strip()

            if url.startswith("["):
                endIndex = webhook.rindex("]")
                endIndex += 1
                subTypes = webhook[:endIndex]
                url = url[endIndex:]

                log.debug("webhook types: %s", subTypes)

                for payloadData in payload:
                    if payloadData["type"] in subTypes:
                        log.debug("Payload to add: %s" % str(payloadData))
                        payloadToSend.append(payloadData)
            else:
                payloadToSend = payload

            if len(payloadToSend) == 0:
                log.debug("Payload is empty")
                continue

            log.debug("Sending to webhook %s", url)
            log.debug("Payload: %s" % str(payloadToSend))
            try:
                response = requests.post(
                    url,
                    data=json.dumps(payloadToSend),
                    headers={"Content-Type": "application/json"},
                    timeout=5,
                )
                if response.status_code != 200:
                    log.warning(
                        "Got status code other than 200 OK from webhook destination: %s"
                        % str(response.status_code)
                    )
                else:
                    log.info(
                        "Successfully sent payload to webhook. Stats: %s",
                        json.dumps(self.__payload_type_count(payloadToSend)),
                    )
            except Exception as e:
                log.warning("Exception occured while sending webhook: %s" % str(e))

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

            # required by PA but not provided by Monocle
            if weather.get("latitude", None) is None:
                weather_payload["latitude"] = S2Helper.middle_of_cell(weather["s2_cell_id"])[0]
            else:
                weather_payload["latitude"] = weather["latitude"]

            if weather.get("longitude", None) is None:
                weather_payload["longitude"] = S2Helper.middle_of_cell(weather["s2_cell_id"])[1]
            else:
                weather_payload["longitude"] = weather["longitude"]

            entire_payload = {"type": "weather", "message": weather_payload}

            ret.append(entire_payload)

        return ret

    def __prepare_raid_data(self, raid_data):
        ret = []

        for raid in raid_data:
            # skip ex raid mon if disabled
            if (
                not self._args.webhook_send_exraids
                and raid.get("pokemon_id") is not None
                and raid.get("pokemon_id") == self.EXRAID_MON_ID
            ):
                continue

            raid_payload = {
                "latitude": raid["latitude"],
                "longitude": raid["longitude"],
                "level": raid["level"],
                "pokemon_id": raid["pokemon_id"],
                "team_id": raid["team_id"],
                "cp": raid["cp"],
                "move_1": raid["move_1"],
                "move_2": raid["move_2"],
                "start": raid["start"],
                "end": raid["end"],
                "name": raid["name"],
            }

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

            # create final message
            entire_payload = {"type": "raid", "message": raid_payload}

            # add to payload
            ret.append(entire_payload)

        return ret

    def __prepare_mon_data(self, mon_data):
        ret = []

        for mon in mon_data:
            mon_payload = {
                "encounter_id": mon["encounter_id"],
                "pokemon_id": mon["pokemon_id"],
                "spawnpoint_id": mon["spawnpoint_id"],
                "latitude": mon["latitude"],
                "longitude": mon["longitude"],
                "disappear_time": mon["disappear_time"],
            }

            # used by RM
            if mon.get("cp_multiplier", None) is not None:
                mon_payload["cp_multiplier"] = mon["cp_multiplier"]
                mon_payload["pokemon_level"] = calculate_mon_level(mon["cp_multiplier"])

            # used by Monocle
            if mon.get("level", None) is not None:
                mon_payload["pokemon_level"] = mon["level"]

            if mon["form"] is not None and mon["form"] > 0:
                mon_payload["form"] = mon["form"]

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

            if (
                mon["weather_boosted_condition"] is not None
                and mon["weather_boosted_condition"] > 0
            ):
                mon_payload["boosted_weather"] = mon["weather_boosted_condition"]

            # create finale message
            entire_payload = {"type": "pokemon", "message": mon_payload}

            # add to payload
            ret.append(entire_payload)

        return ret

    def __prepare_gyms_data(self, gym_data):
        ret = []

        for gym in gym_data:
            gym_payload = {
                "gym_id": gym["gym_id"],
                "latitude": gym["latitude"],
                "longitude": gym["longitude"],
                "team_id": gym["team_id"],
                "name": gym["name"],
                "slots_available": gym["slots_available"],
            }

            if gym["description"] is not None:
                gym_payload["description"] = gym["description"]

            if gym["url"] is not None:
                gym_payload["url"] = gym["url"]

            # create final message
            entire_payload = {"type": "gym", "message": gym_payload}

            # add to payload
            ret.append(entire_payload)

        return ret

    def run_worker(self):
        log.info("Starting webhook worker thread")
        try:
            while True:
                # the payload that is about to be sent
                full_payload = []

                # raids
                raids = self.__prepare_raid_data(
                    self._db_wrapper.get_raids_changed_since(self._last_check)
                )
                full_payload += raids

                # weather
                if self._args.weather_webhook:
                    weather = self.__prepare_weather_data(
                        self._db_wrapper.get_weather_changed_since(self._last_check)
                    )
                    full_payload += weather

                # gyms
                if self._args.gym_webhook:
                    gyms = self.__prepare_gyms_data(
                        self._db_wrapper.get_gyms_changed_since(self._last_check)
                    )
                    full_payload += gyms

                if self._args.pokemon_webhook:
                    mon = self.__prepare_mon_data(
                        self._db_wrapper.get_mon_changed_since(self._last_check)
                    )
                    full_payload += mon

                # send our payload
                self.__send_webhook(full_payload)

                self._last_check = int(time.time())
                time.sleep(self._worker_interval_sec)
        except KeyboardInterrupt:
            # graceful exit
            pass
