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
        return_log = []
        log = self._get_device_updater().get_log(withautojobs=withautojobs)
        for entry in log:
            if 'jobname' not in entry:
                entry['jobname'] = entry.get('file', 'Unknown Name')
            return_log.append(entry)
        return await self._json_response(return_log)
