import time

from aiohttp import web
from loguru import logger

from mapadroid.mitm_receiver.endpoints.AbstractMitmReceiverRootEndpoint import AbstractMitmReceiverRootEndpoint
from mapadroid.utils.collections import Location
from mapadroid.utils.logging import get_logger


class ReceiveProtosEndpoint(AbstractMitmReceiverRootEndpoint):
    """
    "/"
    """

    async def _iter(self):
        # TODO: VisitorPattern for extra auth checks...
        with logger.contextualize(ip=self._get_request_address(), name="endpoint"):
            await self._check_origin_header()
            return await super()._iter()

    # TODO: Auth
    async def post(self):
        data = await self.request.json()
        origin = self.request.headers.get("origin")
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

        await self._get_mitm_mapper().set_injection_status(origin, True)
        return web.Response(status=200)

    async def __handle_proto_data_dict(self, origin: str, data: dict) -> None:
        proto_type = data.get("type", None)
        if proto_type is None or proto_type == 0:
            logger.warning("Could not read method ID. Stopping processing of proto")
            return

        if proto_type not in (106, 102, 101, 104, 4, 156, 145):
            # trash protos - ignoring
            return

        timestamp: float = data.get("timestamp", int(time.time()))
        if self._get_mad_args().mitm_ignore_pre_boot is True and timestamp < self._get_mitmreceiver_startup_time():
            return

        location_of_data: Location = Location(data.get("lat", 0.0), data.get("lng", 0.0))
        if (location_of_data.lat > 90 or location_of_data.lat < -90 or
                location_of_data.lng > 180 or location_of_data.lng < -180):
            location_of_data: Location = Location(0.0, 0.0)
        await self._get_mitm_mapper().update_latest(origin, timestamp_received_raw=timestamp,
                                                    timestamp_received_receiver=time.time(), key=proto_type,
                                                    value=data["payload"],
                                                    location=location_of_data)
        logger.debug2("Placing data received to data_queue")
        await self._add_to_queue((timestamp, data, origin))
