from mapadroid.madmin.RootEndpoint import RootEndpoint


class Reload(RootEndpoint):
    async def get(self):
        await self._get_storage_obj().reload()

