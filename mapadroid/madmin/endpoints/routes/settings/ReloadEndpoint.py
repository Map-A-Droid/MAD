import asyncio

from aiohttp import web
from aiohttp.abc import Request

from mapadroid.db.model import AuthLevel
from mapadroid.madmin.AbstractMadminRootEndpoint import (
    AbstractMadminRootEndpoint, check_authorization_header)


class ReloadEndpoint(AbstractMadminRootEndpoint):
    """
    "/reload"
    """

    def __init__(self, request: Request):
        super().__init__(request)

    @check_authorization_header(AuthLevel.MADMIN_ADMIN)
    async def get(self):
        loop = asyncio.get_running_loop()
        loop.create_task(self._get_mapping_manager().update())
        raise web.HTTPFound(self._url_for("settings_devices"))
