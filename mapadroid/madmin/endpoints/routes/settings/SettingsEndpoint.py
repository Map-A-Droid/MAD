from aiohttp.abc import Request

from mapadroid.db.model import AuthLevel
from mapadroid.madmin.AbstractMadminRootEndpoint import (
    AbstractMadminRootEndpoint, check_authorization_header)


class SettingsEndpoint(AbstractMadminRootEndpoint):
    """
    "/settings"
    """

    def __init__(self, request: Request):
        super().__init__(request)

    @check_authorization_header(AuthLevel.MADMIN_ADMIN)
    async def get(self):
        await self._redirect(self._url_for("settings_devices"))
