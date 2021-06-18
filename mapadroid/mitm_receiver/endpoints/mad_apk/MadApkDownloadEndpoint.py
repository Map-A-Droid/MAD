import json
from typing import Dict
from aiofile import async_open

from mapadroid.mitm_receiver.endpoints.AbstractMitmReceiverRootEndpoint import AbstractMitmReceiverRootEndpoint
from aiohttp import web


class MadApkDownloadEndpoint(AbstractMitmReceiverRootEndpoint):
    """
    "/mad_apk/<string:apk_type>/download"
    "/mad_apk/<string:apk_type>/<string:apk_arch>/download"
    """

    # TODO: Auth/preprocessing for autoconfig?
    async def get(self):
        parsed = self._parse_frontend()
        if type(parsed) == web.Response:
            return parsed
        apk_type, apk_arch = parsed
        return parsed
        # TODO: Restore functionality
        # return stream_package(self._db_wrapper, self.__storage_obj, apk_type, apk_arch)
