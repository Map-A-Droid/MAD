from aiohttp import web

from mapadroid.madmin.endpoints.api.autoconf.AutoconfEndpoint import AutoconfEndpoint
from mapadroid.madmin.endpoints.api.autoconf.AutoconfPdEndpoint import AutoconfPdEndpoint
from mapadroid.madmin.endpoints.api.autoconf.AutoconfRgcEndpoint import AutoconfRgcEndpoint
from mapadroid.madmin.endpoints.api.autoconf.AutoconfStatusEndpoint import AutoconfStatusEndpoint


def register_api_autoconf_endpoints(app: web.Application):
    app.router.add_view('/api/autoconf', AutoconfEndpoint)
    app.router.add_view('/api/autoconf/{session_id}', AutoconfStatusEndpoint)

    app.router.add_view('/api/autoconf/rgc', AutoconfRgcEndpoint)
    app.router.add_view('/api/autoconf/pd', AutoconfPdEndpoint)
