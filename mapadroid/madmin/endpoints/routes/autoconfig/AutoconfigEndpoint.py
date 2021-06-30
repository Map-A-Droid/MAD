from aiohttp import web
from aiohttp.abc import Request

from mapadroid.madmin.AbstractMadminRootEndpoint import AbstractMadminRootEndpoint


class AutoconfigEndpoint(AbstractMadminRootEndpoint):
    def __init__(self, request: Request):
        super().__init__(request)

    # TODO: Auth
    async def get(self):
        raise web.HTTPFound(self._url_for('autoconfig_pending'))
