from aiohttp import web

from mapadroid.madmin.endpoints.api.resources.AreaEndpoint import AreaEndpoint


def register_api_resources_endpoints(app: web.Application):
    app.router.add_view('/api/area', AreaEndpoint)
    app.router.add_view('/api/area/{identifier}', AreaEndpoint)
    # app.router.add_view('/api/autoconf/{session_id}', AutoconfStatusEndpoint)

#    app.router.add_view('/api/autoconf/rgc', AutoconfRgcEndpoint)
#    app.router.add_view('/api/autoconf/pd', AutoconfPdEndpoint)
