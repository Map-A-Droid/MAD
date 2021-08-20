import json
from typing import Dict

from aiofile import async_open
from loguru import logger

from mapadroid.mitm_receiver.endpoints.AbstractMitmReceiverRootEndpoint import AbstractMitmReceiverRootEndpoint


class GetAddressesEndpoint(AbstractMitmReceiverRootEndpoint):
    """
    "/get_addresses"
    """

    async def _iter(self):
        # TODO: VisitorPattern for extra auth checks...
        with logger.contextualize(identifier=self._get_request_address(), name="get_addresses-endpoint"):
            await self._check_origin_header()
            return await super()._iter()

    # TODO: Auth
    async def get(self):
        try:
            supported = await self.get_addresses_read("configs/addresses.json")
        except FileNotFoundError:
            supported = await self.get_addresses_read("configs/version_codes.json")
        return self._json_response(supported)

    @staticmethod
    async def get_addresses_read(path) -> Dict:
        supported: Dict[str, Dict] = {}
        async with async_open(path, 'rb') as fh:
            data = json.loads(await fh.read())
            for key, value in data.items():
                if type(value) is dict:
                    supported[key] = value
                else:
                    supported[key] = {}
        return supported
