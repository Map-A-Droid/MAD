from aiohttp import web

from mapadroid.plugins.endpoints.DownloadPluginEndpoint import \
    DownloadPluginEndpoint
from mapadroid.plugins.endpoints.PluginsEndpoint import PluginsEndpoint
from mapadroid.plugins.endpoints.UploadPluginEndpoint import \
    UploadPluginEndpoint


def register_plugin_endpoints(app: web.Application):
    app.router.add_view('/', PluginsEndpoint, name='plugins')
    app.router.add_view('/upload_plugin', UploadPluginEndpoint, name='upload_plugin')
    app.router.add_view('/download_plugin', DownloadPluginEndpoint, name='download_plugin')
