import asyncio
import time
from typing import Optional, List, Dict

from aiohttp import web
from loguru import logger
from orjson import orjson

from mapadroid.db.helper.SettingsDeviceHelper import SettingsDeviceHelper
from mapadroid.db.helper.TrsStatusHelper import TrsStatusHelper
from mapadroid.db.model import SettingsDevice
from mapadroid.mitm_receiver.endpoints.AbstractMitmReceiverRootEndpoint import AbstractMitmReceiverRootEndpoint
from mapadroid.utils.ProtoIdentifier import ProtoIdentifier
from mapadroid.utils.collections import Location


class ReceiveProtosEndpoint(AbstractMitmReceiverRootEndpoint):
    """
    "/"
    """

    async def _iter(self):
        # TODO: VisitorPattern for extra auth checks...
        with logger.contextualize(identifier=self._get_request_address(), name="receive_protos"):
            await self._check_origin_header()
            return await super()._iter()

    # TODO: Auth
    async def post(self):
        raw_data = await self.request.read()
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(
            None, self.__process_data_to_json, raw_data)
        del raw_data
        origin = self.request.headers.get("origin")
        with logger.contextualize(identifier=origin, name="receive_protos"):
            logger.debug2("Receiving proto")

            logger.debug4("Proto data received {}", data)
            if isinstance(data, list):
                # list of protos... we hope so at least....
                logger.debug2("Receiving list of protos")
                for proto in data:
                    await self.__handle_proto_data_dict(origin, proto)
            elif isinstance(data, dict):
                logger.debug2("Receiving single proto")
                # single proto, parse it...
                await self.__handle_proto_data_dict(origin, data)

            # del data
            return web.Response(status=200)

    def __process_data_to_json(self, raw_data):
        raw_text = raw_data.decode('utf8')
        data = orjson.loads(raw_text)
        del raw_text
        return data

    async def __handle_proto_data_dict(self, origin: str, data: dict) -> None:
        proto_type = data.get("type", None)
        if proto_type is None or proto_type == 0:
            logger.warning("Could not read method ID. Stopping processing of proto")
            return
        timestamp: int = data.get("timestamp", int(time.time()))
        if self._get_mad_args().mitm_ignore_pre_boot is True and timestamp < self._get_mitmreceiver_startup_time():
            return

        if proto_type not in (106, 102, 101, 104, 4, 156, 145):
            # trash protos - ignoring
            return
        elif proto_type == 106 and not data["payload"].get("cells", []):
            logger.debug("Ignoring apparently empty GMO")
            return

        location_of_data: Location = Location(data.get("lat", 0.0), data.get("lng", 0.0))
        if (location_of_data.lat > 90 or location_of_data.lat < -90 or
                location_of_data.lng > 180 or location_of_data.lng < -180):
            location_of_data: Location = Location(0.0, 0.0)
        time_received: int = int(time.time())

        if proto_type == ProtoIdentifier.FORT_SEARCH.value:
            logger.debug("Checking fort search proto type 101")
            await self._handle_fort_search_proto(origin, data["payload"], location_of_data, timestamp)
        quests_held: Optional[List[int]] = data.get("quests_held", None)
        await self._get_mitm_mapper().set_quests_held(origin, quests_held)
        await self._get_mitm_mapper().update_latest(origin, timestamp_received_raw=timestamp,
                                                    timestamp_received_receiver=time_received, key=str(proto_type),
                                                    value=data["payload"],
                                                    location=location_of_data)
        logger.debug2("Placing data received to data_queue")
        await self._add_to_queue((timestamp, data, origin))

    async def _handle_fort_search_proto(self, origin: str, quest_proto: Dict, location_of_data: Location,
                                        timestamp: int) -> None:
        instance_id = self._get_db_wrapper().get_instance_id()
        logger.debug("Checking fort search of {} of instance {}", origin, instance_id)
        device: Optional[SettingsDevice] = await SettingsDeviceHelper.get_by_origin(self._session,
                                                                                    self._get_db_wrapper().get_instance_id(),
                                                                                    origin)

        if device:
            fort_id = quest_proto.get("fort_id", None)
            if fort_id is None:
                logger.debug("No fort id in fort search")
                return
            if "challenge_quest" not in quest_proto:
                logger.debug("No challenge quest in fort search")
                return
            protoquest = quest_proto["challenge_quest"]["quest"]
            rewards = protoquest.get("quest_rewards", None)
            if not rewards:
                logger.debug("No quest rewards in fort search")
                return
            await TrsStatusHelper.set_last_softban_action(self._session,
                                                          self._get_db_wrapper().get_instance_id(),
                                                          device.device_id, location_of_data, timestamp)
            self._commit_trigger = True
        else:
            logger.debug("Device not found")
