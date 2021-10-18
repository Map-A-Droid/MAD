from aiohttp import web

from mapadroid.utils.apk_enums import APKType
from mapadroid.mad_apk.utils import lookup_package_info, supported_pogo_version
from mapadroid.mitm_receiver.endpoints.AbstractMitmReceiverRootEndpoint import AbstractMitmReceiverRootEndpoint
from mapadroid.utils.madGlobals import application_args


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

        (msg, status_code) = await lookup_package_info(self._get_storage_obj(), apk_type, apk_arch)
        if msg:
            if apk_type == APKType.pogo and not await supported_pogo_version(apk_arch, msg.version,
                                                                             application_args.maddev_api_token):
                return web.Response(status=406, text='Supported version not installed')
            else:
                return web.Response(status=status_code, text=msg.version)
        else:
            return web.Response(text="", status=status_code)
