from aiohttp import web

from mapadroid.madmin.endpoints.api.apks.MadApkDownloadEndpoint import MadApkDownloadEndpoint
from mapadroid.madmin.endpoints.api.apks.MadApkEndpoint import MadApkEndpoint
from mapadroid.madmin.endpoints.api.apks.MadApkReloadEndpoint import MadApkReloadEndpoint


def register_api_apk_endpoints(app: web.Application):
    app.router.add_view('/api/mad_apk', MadApkEndpoint, name='api_madapk')
    app.router.add_view('/api/mad_apk/{apk_type}', MadApkEndpoint, name='api_madapk_apk_type')
    app.router.add_view('/api/mad_apk/{apk_type}/{apk_arch}', MadApkEndpoint, name='api_madapk_apk_type_arch')

    # Download GET
    app.router.add_view('/api/mad_apk/{apk_type}/{apk_arch}/download', MadApkDownloadEndpoint,
                        name='api_madapk_apk_download_arch')
    app.router.add_view('/api/mad_apk/{apk_type}/download', MadApkDownloadEndpoint,
                        name='api_madapk_apk_download_noarch')

    # Reload GET
    app.router.add_view('/api/mad_apk/reload', MadApkReloadEndpoint, name='api_madapk_reload')
