import json
from typing import Dict
from aiofile import async_open


from mapadroid.mitm_receiver.endpoints.AbstractMitmReceiverRootEndpoint import AbstractMitmReceiverRootEndpoint
from aiohttp import web


class MadApkInfoEndpoint(AbstractMitmReceiverRootEndpoint):
    """
    "/mad_apk/<string:apk_type>"
    "/mad_apk/<string:apk_type>/<string:apk_arch>"
    """

    # TODO: Auth/preprocessing for autoconfig?
    async def get(self):
        parsed = self._parse_frontend()
        if type(parsed) == web.Response:
            return parsed
        apk_type, apk_arch = parsed
        # TODO: Restore functionality
        return parsed
        # (msg, status_code) = await lookup_package_info(self.__storage_obj, apk_type, apk_arch)
        # if msg:
        #     if apk_type == APKType.pogo and not supported_pogo_version(apk_arch, msg.version):
        #         return Response(status=406, response='Supported version not installed')
        #     return Response(status=status_code, response=msg.version)
        # else:
        #     return Response("", status=status_code)
