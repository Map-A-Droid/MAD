import os
from typing import Dict
from aiohttp import web

import mapadroid.plugins.pluginBase
from plugins.madPluginExample.endoints import register_custom_plugin_endpoints


class MadPluginExample(mapadroid.plugins.pluginBase.Plugin):
    """This plugin is just the identity function: it returns the argument
    """

    def _file_path(self) -> str:
        return os.path.dirname(os.path.abspath(__file__))

    def __init__(self, subapp_to_register_to: web.Application, mad_parts: Dict):
        super().__init__(subapp_to_register_to, mad_parts)

        self._hotlink = [
            ("Plugin faq", "pluginfaq", "Create own plugin"),
            ("Plugin Example", "example", "Testpage"),
        ]

        if self._pluginconfig.getboolean("plugin", "active", fallback=False):
            register_custom_plugin_endpoints(self._subapp)

            for name, link, description in self._hotlink:
                self._mad_parts['madmin'].add_plugin_hotlink(name, link.replace("/", ""),
                                                       self.pluginname, self.description, self.author, self.url,
                                                       description, self.version)

    async def _perform_operation(self):
        # load your stuff now
        return True
