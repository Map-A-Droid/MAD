import aiohttp_jinja2
from aiohttp.abc import Request

from mapadroid.db.model import AuthLevel
from mapadroid.mad_apk.utils import get_apk_status
from mapadroid.madmin.AbstractMadminRootEndpoint import (
    AbstractMadminRootEndpoint, check_authorization_header, expand_context)
from mapadroid.utils.madGlobals import MadGlobals


class ApkEndpoint(AbstractMadminRootEndpoint):
    def __init__(self, request: Request):
        super().__init__(request)

    @check_authorization_header(AuthLevel.MADMIN_ADMIN)
    @aiohttp_jinja2.template('madmin_apk_root.html')
    @expand_context()
    async def get(self):
        return {"apks": await get_apk_status(self._get_storage_obj()),
                "has_token": MadGlobals.application_args.maddev_api_token not in [None, ""]}
