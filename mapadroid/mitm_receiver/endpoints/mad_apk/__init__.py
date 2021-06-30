from aiohttp import web

from mapadroid.mitm_receiver.endpoints.mad_apk.MadApkDownloadEndpoint import MadApkDownloadEndpoint
from mapadroid.mitm_receiver.endpoints.mad_apk.MadApkInfoEndpoint import MadApkInfoEndpoint


def register_mad_apk_endpoints(app: web.Application):
    app.router.add_view('/mad_apk/{apk_type}', MadApkInfoEndpoint, name='mad_apk_info')
    app.router.add_view('/mad_apk/{apk_type}/{apk_arch}', MadApkInfoEndpoint, name='mad_apk_arch_info')
    app.router.add_view('/mad_apk/{apk_type}/download', MadApkDownloadEndpoint, name='mad_apk_download')
    app.router.add_view('/mad_apk/{apk_type}/{apk_arch}/download', MadApkDownloadEndpoint,
                        name='mad_apk_arch_info_download')
