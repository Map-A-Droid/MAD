import aiohttp_jinja2
from aiohttp.abc import Request

from mapadroid.mad_apk.utils import get_apk_status
from mapadroid.madmin.AbstractMadminRootEndpoint import AbstractMadminRootEndpoint
from mapadroid.utils.madGlobals import application_args


class ApkEndpoint(AbstractMadminRootEndpoint):
    def __init__(self, request: Request):
        super().__init__(request)

    @aiohttp_jinja2.template('madmin_apk_root.html')
    async def get(self):
        return {"apks": await get_apk_status(self._get_storage_obj()),
                "has_token": application_args.maddev_api_token not in [None, ""]}
