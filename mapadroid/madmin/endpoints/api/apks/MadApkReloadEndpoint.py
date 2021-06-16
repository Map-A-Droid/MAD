from mapadroid.madmin.AbstractMadminRootEndpoint import AbstractMadminRootEndpoint


class MadApkReloadEndpoint(AbstractMadminRootEndpoint):
    async def get(self):
        await self._get_storage_obj().reload()
