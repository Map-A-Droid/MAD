from aiohttp import web

from plugins.madPluginExample.endoints.ExampleEndpoint import ExampleEndpoint
from plugins.madPluginExample.endoints.PluginfaqEndpoint import PluginfaqEndpoint


def register_custom_plugin_endpoints(app: web.Application):
    # Simply register any endpoints here. If you do not intend to add any views (which is discouraged) simply "pass"
    app.router.add_view('/example', ExampleEndpoint, name='example')
    app.router.add_view('/pluginfaq', PluginfaqEndpoint, name='pluginfaq')
