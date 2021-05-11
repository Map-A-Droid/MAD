from aiohttp_jinja2.helpers import url_for

from mapadroid.madmin.AbstractRootEndpoint import AbstractRootEndpoint


class RootEndpoint(AbstractRootEndpoint):
    """
    "/"
    """

    # TODO: Auth
    async def get(self):
        await self._redirect(url_for("settings"))
