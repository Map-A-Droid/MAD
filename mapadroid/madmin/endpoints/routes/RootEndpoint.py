from mapadroid.madmin.AbstractMadminRootEndpoint import AbstractMadminRootEndpoint


class RootEndpoint(AbstractMadminRootEndpoint):
    """
    "/"
    """

    # TODO: Auth
    async def get(self):
        await self._redirect(self._url_for("settings"))
