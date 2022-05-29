from typing import Optional

from aiohttp import web

from mapadroid.madmin.endpoints.routes.control.AbstractControlEndpoint import \
    AbstractControlEndpoint


class GetInstallLogEndpoint(AbstractControlEndpoint):
    """
    "/get_install_log"
    """

    # TODO: Auth
    async def get(self) -> web.Response:
        withautojobs_raw: Optional[str] = self.request.query.get('withautojobs')
        withautojobs: bool = True if withautojobs_raw == "True" else False
        log = self._get_device_updater().get_log_serialized(including_auto_jobs=withautojobs)
        return await self._json_response(log)
