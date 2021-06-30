from aiohttp import web
from aiohttp.abc import Request

from mapadroid.madmin.AbstractMadminRootEndpoint import AbstractMadminRootEndpoint


class ReloadEndpoint(AbstractMadminRootEndpoint):
    """
    "/reload"
    """

    def __init__(self, request: Request):
        super().__init__(request)

    # TODO: Auth
    async def get(self):
        await self._get_mapping_manager().update()
        raise web.HTTPFound(self._url_for("settings_devices"))
