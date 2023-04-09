from mapadroid.db.model import AuthLevel
from mapadroid.madmin.AbstractMadminRootEndpoint import (
    AbstractMadminRootEndpoint, check_authorization_header)


class MadApkReloadEndpoint(AbstractMadminRootEndpoint):
    @check_authorization_header(AuthLevel.MADMIN_ADMIN)
    async def get(self):
        await self._get_storage_obj().reload()
