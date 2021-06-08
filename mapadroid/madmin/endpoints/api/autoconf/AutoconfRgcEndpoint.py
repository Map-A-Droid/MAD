from aiohttp import web

from mapadroid.madmin.AbstractRootEndpoint import AbstractRootEndpoint
from mapadroid.utils.RGCConfig import RGCConfig
from mapadroid.utils.autoconfig import AutoConfIssue


class AutoconfRgcEndpoint(AbstractRootEndpoint):
    async def post(self) -> web.Response:
        return await self.__save_config()

    async def patch(self) -> web.Response:
        return await self.__save_config()

    async def delete(self) -> web.Response:
        await RGCConfig(self._session, self._get_instance_id(), self._get_mad_args()).delete(self._session)
        return self._json_response()

    async def get(self) -> web.Response:
        data = RGCConfig(self._session, self._get_instance_id(), self._get_mad_args()).contents
        return self._json_response(data=data)

    async def __save_config(self) -> web.Response:
        conf = RGCConfig(self._session, self._get_instance_id(), self._get_mad_args())
        try:
            await conf.save_config(await self.request.json())
        except AutoConfIssue as err:
            return self._json_response(data=err.issues, status=400)
        return self._json_response()
