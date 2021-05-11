from aiohttp import web

from mapadroid.madmin.AbstractRootEndpoint import AbstractRootEndpoint
from mapadroid.utils.autoconfig import PDConfig, AutoConfIssue


class AutoconfPdEndpoint(AbstractRootEndpoint):
    async def post(self) -> web.Response:
        return await self.__save_config()

    async def patch(self) -> web.Response:
        return await self.__save_config()

    async def delete(self) -> web.Response:
        await PDConfig(self._get_mad_args()).delete(self._session)
        return self._json_response()

    async def get(self) -> web.Response:
        data = PDConfig(self._get_mad_args()).contents
        return self._json_response(data=data)

    async def __save_config(self) -> web.Response:
        conf = PDConfig(self._get_mad_args())
        try:
            conf.save_config(self._session, await self.request.json())
        except AutoConfIssue as err:
            return self._json_response(data=err.issues, status=400)
        return self._json_response()
