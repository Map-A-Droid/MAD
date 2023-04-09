from typing import List

from aiohttp import web

from mapadroid.db.helper.AutoconfigRegistrationHelper import \
    AutoconfigRegistrationHelper
from mapadroid.db.model import AuthLevel, AutoconfigRegistration
from mapadroid.madmin.AbstractMadminRootEndpoint import (
    AbstractMadminRootEndpoint, check_authorization_header)


class AutoconfEndpoint(AbstractMadminRootEndpoint):
    @check_authorization_header(AuthLevel.MADMIN_ADMIN)
    async def get(self) -> web.Response:
        entries: List[AutoconfigRegistration] = await AutoconfigRegistrationHelper \
            .get_all_of_instance(self._session, self._get_instance_id(), None)
        if entries:
            return await self._json_response(data=entries)
        else:
            raise web.HTTPNotFound()
