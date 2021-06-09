
from mapadroid.madmin.AbstractRootEndpoint import AbstractRootEndpoint


class RootEndpoint(AbstractRootEndpoint):
    """
    "/"
    """

    # TODO: Auth
    async def get(self):
        await self._redirect(self._url_for("settings"))
