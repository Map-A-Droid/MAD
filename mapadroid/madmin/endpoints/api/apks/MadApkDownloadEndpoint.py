from aiohttp import web

from mapadroid.mad_apk.utils import convert_to_backend, stream_package
from mapadroid.madmin.AbstractRootEndpoint import AbstractRootEndpoint


class MadApkDownloadEndpoint(AbstractRootEndpoint):
    # TODO: Require auth
    async def get(self):
        response = web.StreamResponse()
        apk_type_raw: str = self.request.match_info['apk_type']
        apk_arch_raw: str = self.request.match_info['apk_arch']

        apk_type, apk_arch = convert_to_backend(apk_type_raw, apk_arch_raw)

        data_generator, mimetype, filename = stream_package(self._session, self._get_storage_obj(), apk_type, apk_arch)
        response.content_type = mimetype
        response.headers['Content-Disposition'] = 'attachment; filename={}'.format(filename)
        await response.prepare(self.request)
        async for data in data_generator:
            await response.write(data)
        return response
