from aiohttp import web

from mapadroid.madmin.endpoints.api.autoconf.AutoconfEndpoint import AutoconfEndpoint
from mapadroid.madmin.endpoints.api.autoconf.AutoconfPdEndpoint import AutoconfPdEndpoint
from mapadroid.madmin.endpoints.api.autoconf.AutoconfRgcEndpoint import AutoconfRgcEndpoint
from mapadroid.madmin.endpoints.api.autoconf.AutoconfStatusEndpoint import AutoconfStatusEndpoint


def register_api_autoconf_endpoints(app: web.Application):
    app.router.add_view('/api/autoconf/{session_id}', AutoconfStatusEndpoint, name='api_autoconf_status')
    app.router.add_view('/api/autoconf', AutoconfEndpoint, name='api_autoconf')
    app.router.add_view('/api/autoconf/rgc', AutoconfRgcEndpoint, name='api_autoconf_rgc')
    app.router.add_view('/api/autoconf/pd', AutoconfPdEndpoint, name='api_autoconf_pd')
