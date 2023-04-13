from typing import List

from aiohttp import web
from aiohttp.abc import Request

from mapadroid.db.helper.AutoconfigLogsHelper import AutoconfigLogsHelper
from mapadroid.db.helper.AutoconfigRegistrationHelper import \
    AutoconfigRegistrationHelper
from mapadroid.db.model import AuthLevel, AutoconfigLog, AutoconfigRegistration
from mapadroid.madmin.AbstractMadminRootEndpoint import (
    AbstractMadminRootEndpoint, check_authorization_header)


class AutoconfigLogsEndpointUpdate(AbstractMadminRootEndpoint):
    """
    "/autoconfig/logs/<int:session_id>/update"
    TODO: Move to /api/?
    """

    def __init__(self, request: Request):
        super().__init__(request)

    @check_authorization_header(AuthLevel.MADMIN_ADMIN)
    async def get(self):
        session_id: int = int(self.request.match_info['session_id'])

        sessions: List[AutoconfigRegistration] = await AutoconfigRegistrationHelper \
            .get_all_of_instance(self._session, instance_id=self._get_instance_id(), session_id=session_id)
        if not sessions:
            raise web.HTTPNotFound()
        logs: List[AutoconfigLog] = await AutoconfigLogsHelper.get_all_of_instance(self._session,
                                                                                   self._get_instance_id(),
                                                                                   session_id)
        return await self._json_response(logs)
