import json
from typing import Optional, Dict
from aiofile import async_open


from mapadroid.mitm_receiver.endpoints.AbstractMitmReceiverRootEndpoint import AbstractMitmReceiverRootEndpoint


class GetAddresses(AbstractMitmReceiverRootEndpoint):
    """
    "/get_addresses"
    """

    # TODO: Auth
    async def get(self):
        supported: Dict[str, Dict] = {}
        try:
            supported = await self.get_addresses_read("configs/addresses.json")
        except FileNotFoundError:
            supported = await self.get_addresses_read("configs/version_codes.json")
        return supported

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