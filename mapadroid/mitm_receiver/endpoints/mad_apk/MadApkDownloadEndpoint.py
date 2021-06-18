from aiohttp import web

from mapadroid.mad_apk.utils import stream_package
from mapadroid.mitm_receiver.endpoints.AbstractMitmReceiverRootEndpoint import AbstractMitmReceiverRootEndpoint


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
        response = web.StreamResponse()

        data_generator, mimetype, filename = stream_package(self._session, self._get_storage_obj(), apk_type, apk_arch)
        response.content_type = mimetype
        response.headers['Content-Disposition'] = 'attachment; filename={}'.format(filename)
        await response.prepare(self.request)
        async for data in data_generator:
            await response.write(data)
        return response
