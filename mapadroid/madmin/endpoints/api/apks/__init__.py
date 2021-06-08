from aiohttp import web

from mapadroid.madmin.endpoints.api.apks.MadApkDownloadEndpoint import MadApkDownloadEndpoint
from mapadroid.madmin.endpoints.api.apks.MadApkEndpoint import MadApkEndpoint
from mapadroid.madmin.endpoints.api.apks.MadApkReloadEndpoint import MadApkReloadEndpoint


def register_api_apk_endpoints(app: web.Application):
    app.router.add_view('/api/mad_apk', MadApkEndpoint)
    app.router.add_view('/api/mad_apk/{apk_type}', MadApkEndpoint)
    app.router.add_view('/api/mad_apk/{apk_type}/{apk_arch}', MadApkEndpoint)

    # Download GET
    app.router.add_view('/api/mad_apk/{apk_type}/{apk_arch}/download', MadApkDownloadEndpoint)
    app.router.add_view('/api/mad_apk/{apk_type}/download', MadApkDownloadEndpoint)

    # Reload GET
    app.router.add_view('/api/mad_apk/reload', MadApkReloadEndpoint)

