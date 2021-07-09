from typing import List

from aiohttp import web

from mapadroid.db.helper.AutoconfigRegistrationHelper import AutoconfigRegistrationHelper
from mapadroid.db.model import AutoconfigRegistration
from mapadroid.madmin.AbstractMadminRootEndpoint import AbstractMadminRootEndpoint


class AutoconfEndpoint(AbstractMadminRootEndpoint):
    async def get(self) -> web.Response:
        entries: List[AutoconfigRegistration] = await AutoconfigRegistrationHelper \
            .get_all_of_instance(self._session, self._get_instance_id(), None)
        if entries:
            return await self._json_response(data=entries)
        else:
            raise web.HTTPNotFound()
