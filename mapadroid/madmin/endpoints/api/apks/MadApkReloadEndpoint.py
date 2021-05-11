from mapadroid.madmin.AbstractRootEndpoint import AbstractRootEndpoint


class MadApkReloadEndpoint(AbstractRootEndpoint):
    async def get(self):
        await self._get_storage_obj().reload()
