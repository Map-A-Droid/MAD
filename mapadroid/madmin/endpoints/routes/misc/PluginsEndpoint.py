import aiohttp_jinja2

from mapadroid.madmin.AbstractRootEndpoint import AbstractRootEndpoint


class PluginsEndpoint(AbstractRootEndpoint):
    """
    "/plugins"
    """

    # TODO: Auth
    @aiohttp_jinja2.template('plugins.html')
    async def get(self):
        plugins = {}
        plugin_hotlinks = self._get_plugin_hotlinks()
        if plugin_hotlinks:
            for plugin in plugin_hotlinks:
                if plugin['author'] not in plugins:
                    plugins[plugin['author']] = {}

                if plugin['Plugin'] not in plugins[plugin['author']]:
                    plugins[plugin['author']][plugin['Plugin']] = {}
                    plugins[plugin['author']][plugin['Plugin']]['links'] = []

                plugins[plugin['author']][plugin['Plugin']]['authorurl'] = plugin['authorurl']
                plugins[plugin['author']][plugin['Plugin']]['version'] = plugin['version']
                plugins[plugin['author']][plugin['Plugin']]['description'] = plugin['description']
                plugins[plugin['author']][plugin['Plugin']]['links'].append({'linkname': plugin['linkname'],
                                                                             'linkurl': plugin['linkurl'],
                                                                             'description': plugin['linkdescription']})
        return {
            "title": "Select plugin",
            "time": self._get_mad_args().madmin_time,
            "responsive": str(self._get_mad_args().madmin_noresponsive).lower(),
            "plugin_hotlinks": plugins
        }
