from aiohttp import web

from mapadroid.madmin.endpoints.routes.control.AbstractControlEndpoint import \
    AbstractControlEndpoint


class TakeScreenshotEndpoint(AbstractControlEndpoint):
    """
    "/take_screenshot"
    """

    async def get(self) -> web.Response:
        creationdate = await self._take_screenshot()
        return web.Response(text=creationdate)
