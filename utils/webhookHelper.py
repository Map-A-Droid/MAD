import asyncio
import functools
import json
import os
import time

import logging
from threading import current_thread, Event, Thread
from utils.questGen import generate_quest
from utils.language import open_json_file

import requests
from s2sphere import Cell, CellId, LatLng

log = logging.getLogger(__name__)

quest_webhook_payload = """[{{
      "message": {{
                "pokestop_id": "{pokestop_id}",
                "latitude": {latitude},
                "longitude": {longitude},
                "quest_type": "{quest_type}",
                "quest_type_raw": {quest_type_raw},
                "item_type": "{item_type}",
                "item_amount": {item_amount},
                "item_id": {item_id},
                "pokemon_id": {pokemon_id},
                "name": "{name}",
                "url": "{url}",
                "timestamp": {timestamp},
                "quest_reward_type": "{quest_reward_type}",
                "quest_reward_type_raw": {quest_reward_type_raw},
                "quest_target": {quest_target},
                "quest_task": "{quest_task}",
                "quest_condition": {quest_condition}
        }},
      "type": "quest"
   }} ]"""


plain_webhook = """[{plain}]"""


class WebhookHelper(object):
    def __init__(self, args):
        self.__application_args = args
        self.pokemon_file = open_json_file('pokemon')
        self.gyminfo = None
        self.gyminfo_refresh = None

        self.loop = None
        self.loop_started = Event()
        self.loop_tid = None
        self.t_asyncio_loop = Thread(name='webhook_asyncio_loop', target=self.__start_asyncio_loop)
        self.t_asyncio_loop.daemon = False
        self.t_asyncio_loop.start()

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

    def stop_helper(self):
        self.loop.call_soon_threadsafe(self.loop.stop)

    def __sendToWebhook(self, payload):
        webhooks = self.__application_args.webhook_url.split(',')

        for webhook in webhooks:
            url = webhook.strip()

            if 'bookofquests' in url and 'quest_type' not in payload[0]['message']:
                log.debug("Do not send non-quest webhook to bookofquests")
                return

            log.debug("Sending to webhook %s", url)
            log.debug("Payload: %s" % json.dumps(payload))

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
                log.warning("Exception occured while sending webhook: %s" % str(e))

    # TODO well yeah, this is kinda stupid actually.
    # better solution: actually pass all the information to
    # te webhook helper directly without it accessing the db
    # to retrieve correct DB data like gym name etc
    def set_db_wrapper(self, dbwrapper):
        self.db_wrapper = dbwrapper

    def submit_quest_webhook(self, rawquest):
        if self.__application_args.webhook:
            self.__add_task_to_loop(self._submit_quest_webhook(rawquest))

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
            pokemon_id=int(quest['pokemon_id']),
            item_amount=quest['item_amount'],
            item_id=quest['item_id'],
            quest_task=quest['quest_task'],
            quest_condition=quest['quest_condition'].replace('\'', '"').lower(),
            quest_template=quest['quest_template'])

        payload = json.loads(data)
        self.__sendToWebhook(payload)
