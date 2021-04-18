from aiohttp import web
from aiohttp.abc import Request
from aiohttp_jinja2.helpers import url_for

from mapadroid.madmin.RootEndpoint import RootEndpoint


class AutoconfigEndpoint(RootEndpoint):
    def __init__(self, request: Request):
        super().__init__(request)

    # TODO: Auth
    async def get(self):
        raise web.HTTPFound(url_for('autoconfig_pending'))
