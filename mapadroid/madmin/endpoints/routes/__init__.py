from aiohttp import web

from mapadroid.madmin.endpoints.routes.RootEndpoint import RootEndpoint


def register_routes_root_endpoints(app: web.Application):
    app.router.add_view('/', RootEndpoint, name="root")
