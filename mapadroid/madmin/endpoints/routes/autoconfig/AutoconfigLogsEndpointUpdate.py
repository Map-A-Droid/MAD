from typing import List, Tuple

from aiohttp import web
from aiohttp.abc import Request

from mapadroid.db.helper.AutoconfigLogsHelper import AutoconfigLogHelper
from mapadroid.db.helper.AutoconfigRegistrationHelper import AutoconfigRegistrationHelper
from mapadroid.db.model import AutoconfigRegistration
from mapadroid.madmin.AbstractMadminRootEndpoint import AbstractMadminRootEndpoint


class AutoconfigLogsEndpointUpdate(AbstractMadminRootEndpoint):
    """
    "/autoconfig/logs/<int:session_id>/update"
    TODO: Move to /api/?
    """

    def __init__(self, request: Request):
        super().__init__(request)

    # TODO: Auth
    async def get(self):
        session_id: int = int(self.request.match_info['session_id'])

        sessions: List[AutoconfigRegistration] = await AutoconfigRegistrationHelper \
            .get_all_of_instance(self._session, instance_id=self._get_instance_id(), session_id=session_id)
        if not sessions:
            raise web.HTTPFound("")
        logs: List[Tuple[int, int, str]] = await AutoconfigLogHelper.get_transformed(self._session,
                                                                                     self._get_instance_id())

        return self._json_response(logs)
