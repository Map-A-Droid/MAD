from typing import List

import aiohttp_jinja2
from aiohttp import web
from aiohttp.abc import Request

from mapadroid.db.helper.AutoconfigRegistrationHelper import \
    AutoconfigRegistrationHelper
from mapadroid.db.model import AuthLevel, AutoconfigRegistration
from mapadroid.madmin.AbstractMadminRootEndpoint import (
    AbstractMadminRootEndpoint, check_authorization_header, expand_context)


class AutoconfigLogsEndpoint(AbstractMadminRootEndpoint):
    """
    "/autoconfig/logs/<int:session_id>"
    """

    def __init__(self, request: Request):
        super().__init__(request)

    @check_authorization_header(AuthLevel.MADMIN_ADMIN)
    @aiohttp_jinja2.template('autoconfig_logs.html')
    @expand_context()
    async def get(self):
        session_id: int = int(self.request.match_info['session_id'])

        sessions: List[AutoconfigRegistration] = await AutoconfigRegistrationHelper \
            .get_all_of_instance(self._session, instance_id=self._get_instance_id(), session_id=session_id)

        if not sessions:
            raise web.HTTPFound(self._url_for('autoconfig_pending'))
        return {"subtab": "autoconf_dev",
                "responsive": str(self._get_mad_args().madmin_noresponsive).lower(),
                "session_id": session_id
                }
