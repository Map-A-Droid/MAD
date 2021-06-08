from aiohttp import web

from mapadroid.madmin.endpoints.api.resources.AreaEndpoint import AreaEndpoint
from mapadroid.madmin.endpoints.api.resources.AuthEndpoint import AuthEndpoint


def register_api_resources_endpoints(app: web.Application):
    app.router.add_view('/api/area', AreaEndpoint)
    app.router.add_view('/api/area/{identifier}', AreaEndpoint)

    app.router.add_view('/api/auth', AuthEndpoint)
    app.router.add_view('/api/auth/{identifier}', AuthEndpoint)
