from aiohttp import web

from mapadroid.madmin.endpoints.routes.autoconfig.AutoconfigDownloadEndpoint import AutoconfigDownloadEndpoint
from mapadroid.madmin.endpoints.routes.autoconfig.AutoconfigEndpoint import AutoconfigEndpoint
from mapadroid.madmin.endpoints.routes.autoconfig.AutoconfigLogsEndpoint import AutoconfigLogsEndpoint
from mapadroid.madmin.endpoints.routes.autoconfig.AutoconfigLogsEndpointUpdate import AutoconfigLogsEndpointUpdate
from mapadroid.madmin.endpoints.routes.autoconfig.AutoconfigPdEndpoint import AutoconfigPdEndpoint
from mapadroid.madmin.endpoints.routes.autoconfig.AutoconfigPendingEndpoint import AutoconfigPendingEndpoint
from mapadroid.madmin.endpoints.routes.autoconfig.AutoconfigRgcEndpoint import AutoconfigRgcEndpoint


def register_routes_autoconfig_endpoints(app: web.Application):
    app.router.add_view('/autoconfig', AutoconfigEndpoint, name='autoconfig_root')
    app.router.add_view('/autoconfig/pending', AutoconfigPendingEndpoint, name='autoconfig_pending')
    app.router.add_view('/autoconfig/pending/{session_id}', AutoconfigPendingEndpoint, name='autoconfig_pending_dev')
    app.router.add_view('/autoconfig/logs/{session_id}', AutoconfigLogsEndpoint, name='autoconf_logs')
    app.router.add_view('/autoconfig/logs/{session_id}/update', AutoconfigLogsEndpointUpdate, name='autoconf_logs_get')
    app.router.add_view('/autoconfig/rgc', AutoconfigRgcEndpoint, name='autoconf_rgc')
    app.router.add_view('/autoconfig/pd', AutoconfigPdEndpoint, name='autoconf_pd')
    app.router.add_view('/autoconfig/download', AutoconfigDownloadEndpoint, name='autoconfig_download_file')

