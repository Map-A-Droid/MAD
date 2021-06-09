from aiohttp import web

from mapadroid.madmin.endpoints.routes.apk.ApkEndpoint import ApkEndpoint
from mapadroid.madmin.endpoints.routes.apk.ApkUpdateStatusEndpoint import ApkUpdateStatusEndpoint


def register_routes_apk_endpoints(app: web.Application):
    app.router.add_view('/apk', ApkEndpoint)

    app.router.add_view('/apk_update_status', ApkUpdateStatusEndpoint)
