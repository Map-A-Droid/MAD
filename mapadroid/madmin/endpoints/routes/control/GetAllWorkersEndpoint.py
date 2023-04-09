from aiohttp import web

from mapadroid.madmin.endpoints.routes.control.AbstractControlEndpoint import \
    AbstractControlEndpoint


class GetAllWorkersEndpoint(AbstractControlEndpoint):
    """
    "/get_all_workers"
    """

    async def get(self) -> web.Response:
        devices = await self._get_mapping_manager().get_all_devicenames()
        devicesreturn = []
        for device in devices:
            devicesreturn.append({'worker': device})

        return await self._json_response(devicesreturn)
