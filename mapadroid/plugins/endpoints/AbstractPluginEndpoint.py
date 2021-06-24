import configparser
from abc import ABC

from mapadroid.madmin.AbstractMadminRootEndpoint import AbstractMadminRootEndpoint


class AbstractPluginEndpoint(AbstractMadminRootEndpoint, ABC):
    # TODO: '%s/<string:identifier>' optionally at the end of the route
    # TODO: ResourceEndpoint class that loads the identifier accordingly before patch/post etc are called (populate_mode)

    @staticmethod
    def get_plugin_version(plugin_folder):
        plugin_config = configparser.ConfigParser()
        plugin_config.read(plugin_folder + "/version.mpl")
        return plugin_config.get("plugin", "version", fallback="unknown")

    def _get_plugin_package(self):
        return self.request.app["plugin_package"]

    def _get_plugins(self):
        return self.request.app["plugins"]
