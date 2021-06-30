from aiohttp.abc import Request

from mapadroid.madmin.AbstractMadminRootEndpoint import AbstractMadminRootEndpoint


class SettingsEndpoint(AbstractMadminRootEndpoint):
    """
    "/settings"
    """

    def __init__(self, request: Request):
        super().__init__(request)

    # TODO: Auth
    async def get(self):
        await self._redirect(self._url_for("settings_devices"))
