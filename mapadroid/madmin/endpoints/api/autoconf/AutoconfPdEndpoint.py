from aiohttp import web

from mapadroid.madmin.AbstractMadminRootEndpoint import AbstractMadminRootEndpoint
from mapadroid.utils.PDConfig import PDConfig
from mapadroid.utils.autoconfig import AutoConfIssue


class AutoconfPdEndpoint(AbstractMadminRootEndpoint):
    async def post(self) -> web.Response:
        return await self.__save_config()

    async def patch(self) -> web.Response:
        return await self.__save_config()

    async def delete(self) -> web.Response:
        await PDConfig(self._session, self._get_instance_id(), self._get_mad_args()).delete(self._session)
        self._commit_trigger = True
        return self._json_response()

    async def get(self) -> web.Response:
        config = PDConfig(self._session, self._get_instance_id(), self._get_mad_args())
        await config.load_config()
        return self._json_response(data=config.contents)

    async def __save_config(self) -> web.Response:
        conf = PDConfig(self._session, self._get_instance_id(), self._get_mad_args())
        await conf.load_config()
        try:
            await conf.save_config(await self.request.json())
            self._commit_trigger = True
        except AutoConfIssue as err:
            return self._json_response(data=err.issues, status=400)
        return web.Response(status=200)
