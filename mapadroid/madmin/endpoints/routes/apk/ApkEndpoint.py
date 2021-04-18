import base64
from typing import List, Optional, Dict

import aiohttp_jinja2
from aiohttp.abc import Request

from mapadroid.mad_apk import get_apk_status
from mapadroid.madmin.RootEndpoint import RootEndpoint


class ApkEndpoint(RootEndpoint):
    def __init__(self, request: Request):
        super().__init__(request)

    @aiohttp_jinja2.template('madmin_apk_root.html')
    async def get(self):
        return {"apks": await get_apk_status(self._get_storage_obj())}
