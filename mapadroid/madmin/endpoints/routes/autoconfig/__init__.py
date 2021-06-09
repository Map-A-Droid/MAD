from aiohttp import web

from mapadroid.madmin.endpoints.routes.autoconfig.AutoconfigDownloadEndpoint import AutoconfigDownloadEndpoint
from mapadroid.madmin.endpoints.routes.autoconfig.AutoconfigEndpoint import AutoconfigEndpoint
from mapadroid.madmin.endpoints.routes.autoconfig.AutoconfigLogsEndpoint import AutoconfigLogsEndpoint
from mapadroid.madmin.endpoints.routes.autoconfig.AutoconfigLogsEndpointUpdate import AutoconfigLogsEndpointUpdate
from mapadroid.madmin.endpoints.routes.autoconfig.AutoconfigPdEndpoint import AutoconfigPdEndpoint
from mapadroid.madmin.endpoints.routes.autoconfig.AutoconfigPendingEndpoint import AutoconfigPendingEndpoint
from mapadroid.madmin.endpoints.routes.autoconfig.AutoconfigRgcEndpoint import AutoconfigRgcEndpoint


def register_routes_autoconfig_endpoints(app: web.Application):
    app.router.add_view('/autoconfig', AutoconfigEndpoint)
    app.router.add_view('/autoconfig/pending', AutoconfigPendingEndpoint)
    app.router.add_view('/autoconfig/pending/{session_id}', AutoconfigPendingEndpoint)
    app.router.add_view('/autoconfig/logs/{session_id}', AutoconfigLogsEndpoint)
    app.router.add_view('/autoconfig/logs/{session_id}/update', AutoconfigLogsEndpointUpdate)
    app.router.add_view('/autoconfig/rgc', AutoconfigRgcEndpoint)
    app.router.add_view('/autoconfig/pd', AutoconfigPdEndpoint)
    app.router.add_view('/autoconfig/download', AutoconfigDownloadEndpoint)

